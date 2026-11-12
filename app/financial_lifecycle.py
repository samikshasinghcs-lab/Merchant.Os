"""Tenant-scoped MerchantOS financial lifecycle API.

This module records estimates separately from realized values. It never performs
payment-provider writes or inventory movements. PayPal money movement remains in
the existing approval/execution service; inventory execution requires an external
warehouse integration and is deliberately represented as an auditable instruction.
"""
from __future__ import annotations
import uuid
import os
import hashlib
import mimetypes
from pathlib import Path
from datetime import datetime, timezone, timedelta
from decimal import Decimal, InvalidOperation
from typing import Any
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from fastapi.responses import FileResponse
from sqlalchemy import String, Text, DateTime, Numeric, Integer, ForeignKey, UniqueConstraint, Index, JSON, select, func, text
from sqlalchemy.orm import Mapped, mapped_column
from .orm_base import Base
from . import auth as identity
from .tenant_db import tenant_session
from .domain_models import TenantOrder, TenantReview, TenantAuditEvent, TenantEvidence
from .completion_models import FinancialExecution, FinancialApprovalRequest

router=APIRouter(prefix="/api/v1/financial-lifecycle",tags=["financial-lifecycle"])
MAX_CASE_EVIDENCE_FILES = 8
MAX_CASE_EVIDENCE_BYTES = 5 * 1024 * 1024

def enforce_evidence_capacity(existing_count: int) -> None:
    if existing_count >= MAX_CASE_EVIDENCE_FILES:
        raise HTTPException(409, f"Maximum of {MAX_CASE_EVIDENCE_FILES} evidence items per case reached")

def utcnow(): return datetime.now(timezone.utc)
def principal(p=Depends(identity.current_principal)):
    if not identity.AUTH_AVAILABLE: raise HTTPException(503,"Identity dependencies unavailable")
    return p
def dec(v:Any,field:str,allow_zero=True)->Decimal:
    try:
        x=Decimal(str(v))
        if not x.is_finite() or x!=x.quantize(Decimal("0.01")): raise ValueError()
        if x < 0 or (not allow_zero and x==0): raise ValueError()
        return x.quantize(Decimal("0.01"))
    except Exception: raise HTTPException(400,f"{field} must be a valid non-negative decimal with at most 2 decimal places")
def role(p,allowed):
    if p["role"] not in allowed: raise HTTPException(403,"Insufficient workspace role")

def validate_case_evidence_limits(current_count: int, incoming_bytes: int) -> None:
    if current_count >= MAX_CASE_EVIDENCE_FILES:
        raise HTTPException(409, f"Maximum of {MAX_CASE_EVIDENCE_FILES} evidence items per case reached")
    if incoming_bytes <= 0 or incoming_bytes > MAX_CASE_EVIDENCE_BYTES:
        raise HTTPException(413, "Evidence file must be between 1 byte and 5 MB")
def audit(s,p,event,etype,eid,detail):
    s.add(TenantAuditEvent(id=str(uuid.uuid4()),tenant_id=p["tenant_id"],actor_user_id=p["user_id"],event=event,entity_type=etype,entity_id=eid,detail=detail))

class OrderCost(Base):
    __tablename__="financial_order_costs"
    __table_args__=(UniqueConstraint("tenant_id","order_id",name="uq_fin_cost_tenant_order"),Index("ix_fin_cost_tenant","tenant_id"))
    id:Mapped[str]=mapped_column(String(36),primary_key=True)
    tenant_id:Mapped[str]=mapped_column(String(36),nullable=False,index=True)
    order_id:Mapped[str]=mapped_column(String(100),nullable=False,index=True)
    cogs:Mapped[Decimal]=mapped_column(Numeric(14,2),default=0,nullable=False)
    shipping_out:Mapped[Decimal]=mapped_column(Numeric(14,2),default=0,nullable=False)
    payment_fee:Mapped[Decimal]=mapped_column(Numeric(14,2),default=0,nullable=False)
    packaging:Mapped[Decimal]=mapped_column(Numeric(14,2),default=0,nullable=False)
    other_cost:Mapped[Decimal]=mapped_column(Numeric(14,2),default=0,nullable=False)
    updated_by:Mapped[str]=mapped_column(String(36),nullable=False)
    updated_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=utcnow,nullable=False)

class ResolutionCase(Base):
    __tablename__="financial_resolution_cases"
    __table_args__=(Index("ix_fin_case_tenant_status","tenant_id","status"),Index("ix_fin_case_cluster","tenant_id","complaint_cluster_id"))
    id:Mapped[str]=mapped_column(String(36),primary_key=True)
    tenant_id:Mapped[str]=mapped_column(String(36),nullable=False,index=True)
    order_id:Mapped[str]=mapped_column(String(100),nullable=False,index=True)
    case_type:Mapped[str]=mapped_column(String(24),nullable=False)
    status:Mapped[str]=mapped_column(String(40),nullable=False,default="OPEN")
    reason:Mapped[str]=mapped_column(Text,nullable=False)
    complaint_cluster_id:Mapped[str|None]=mapped_column(String(100))
    requested_amount:Mapped[Decimal]=mapped_column(Numeric(14,2),default=0,nullable=False)
    estimated_loss:Mapped[Decimal]=mapped_column(Numeric(14,2),default=0,nullable=False)
    realized_loss:Mapped[Decimal|None]=mapped_column(Numeric(14,2))
    recoverable_inventory_estimate:Mapped[Decimal]=mapped_column(Numeric(14,2),default=0,nullable=False)
    recovered_inventory_actual:Mapped[Decimal|None]=mapped_column(Numeric(14,2))
    return_reason_code:Mapped[str|None]=mapped_column(String(50))
    exchange_reference:Mapped[str|None]=mapped_column(String(128))
    provider_reference:Mapped[str|None]=mapped_column(String(128))
    created_by:Mapped[str]=mapped_column(String(36),nullable=False)
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=utcnow,nullable=False)
    updated_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=utcnow,nullable=False)

class InventoryDisposition(Base):
    __tablename__="financial_inventory_dispositions"
    __table_args__=(Index("ix_fin_inventory_tenant_case","tenant_id","case_id"),)
    id:Mapped[str]=mapped_column(String(36),primary_key=True)
    tenant_id:Mapped[str]=mapped_column(String(36),nullable=False,index=True)
    case_id:Mapped[str]=mapped_column(String(36),nullable=False,index=True)
    sku:Mapped[str|None]=mapped_column(String(100))
    quantity:Mapped[int]=mapped_column(Integer,default=1,nullable=False)
    disposition:Mapped[str]=mapped_column(String(30),nullable=False)
    estimated_recovery:Mapped[Decimal]=mapped_column(Numeric(14,2),default=0,nullable=False)
    realized_recovery:Mapped[Decimal|None]=mapped_column(Numeric(14,2))
    warehouse_reference:Mapped[str|None]=mapped_column(String(128))
    note:Mapped[str|None]=mapped_column(Text)
    created_by:Mapped[str]=mapped_column(String(36),nullable=False)
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=utcnow,nullable=False)

class JournalEntry(Base):
    __tablename__="financial_journal_entries"
    __table_args__=(UniqueConstraint("tenant_id","idempotency_key",name="uq_fin_journal_idem"),Index("ix_fin_journal_tenant_date","tenant_id","posted_at"))
    id:Mapped[str]=mapped_column(String(36),primary_key=True)
    tenant_id:Mapped[str]=mapped_column(String(36),nullable=False,index=True)
    idempotency_key:Mapped[str]=mapped_column(String(128),nullable=False)
    source_type:Mapped[str]=mapped_column(String(40),nullable=False)
    source_id:Mapped[str]=mapped_column(String(128),nullable=False)
    currency:Mapped[str]=mapped_column(String(3),nullable=False)
    description:Mapped[str]=mapped_column(Text,nullable=False)
    lines:Mapped[list]=mapped_column(JSON,nullable=False)
    posted_by:Mapped[str]=mapped_column(String(36),nullable=False)
    posted_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=utcnow,nullable=False)

class FinancialEvent(Base):
    __tablename__="financial_lifecycle_events"
    __table_args__=(Index("ix_fin_event_tenant_case","tenant_id","case_id","created_at"),)
    id:Mapped[str]=mapped_column(String(36),primary_key=True)
    tenant_id:Mapped[str]=mapped_column(String(36),nullable=False,index=True)
    case_id:Mapped[str]=mapped_column(String(36),nullable=False,index=True)
    event_type:Mapped[str]=mapped_column(String(60),nullable=False)
    actor_id:Mapped[str]=mapped_column(String(36),nullable=False)
    payload:Mapped[dict]=mapped_column(JSON,default=dict,nullable=False)
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=utcnow,nullable=False)


def fisher_exact_two_sided(a:int,b:int,c:int,d:int)->float:
    """Two-sided Fisher exact p-value for a 2x2 table, pure Python."""
    from math import comb
    row1=a+b; row2=c+d; col1=a+c; total=row1+row2
    if total==0: return 1.0
    lo=max(0,col1-row2); hi=min(row1,col1)
    denom=comb(total,row1)
    def prob(x): return comb(col1,x)*comb(total-col1,row1-x)/denom
    observed=prob(a)
    return min(1.0,sum(prob(x) for x in range(lo,hi+1) if prob(x)<=observed+1e-12))

def perceptual_hash(data: bytes) -> str | None:
    """Small pure-Pillow DCT perceptual hash for near-duplicate image detection."""
    try:
        from PIL import Image, ImageOps
        import io, math
        image=Image.open(io.BytesIO(data)).convert("L").resize((32,32))
        pixels=list(image.tobytes())
        coeff=[]
        # Low-frequency 8x8 DCT; 32x32 input keeps the calculation bounded.
        for u in range(8):
            for v in range(8):
                total=0.0
                for y in range(32):
                    for x in range(32):
                        total += pixels[y*32+x]*math.cos((2*x+1)*u*math.pi/64)*math.cos((2*y+1)*v*math.pi/64)
                coeff.append(total)
        median=sorted(coeff[1:])[len(coeff[1:])//2]
        return "".join("1" if value>median else "0" for value in coeff)
    except Exception:
        return None

def hamming_hash_distance(left: str, right: str) -> int:
    if len(left)!=len(right): return 999
    return sum(a!=b for a,b in zip(left,right))

def case_dict(x):
    return {k:(str(getattr(x,k)) if getattr(x,k) is not None and k in {"requested_amount","estimated_loss","realized_loss","recoverable_inventory_estimate","recovered_inventory_actual"} else getattr(x,k)) for k in ["id","order_id","case_type","status","reason","complaint_cluster_id","requested_amount","estimated_loss","realized_loss","recoverable_inventory_estimate","recovered_inventory_actual","return_reason_code","exchange_reference","provider_reference","created_at","updated_at"]}

@router.get("/overview")
def overview(p=Depends(principal)):
    t=p["tenant_id"]
    with tenant_session(t) as s:
        orders=s.scalars(select(TenantOrder).where(TenantOrder.tenant_id==t)).all()
        costs=s.scalars(select(OrderCost).where(OrderCost.tenant_id==t)).all()
        cases=s.scalars(select(ResolutionCase).where(ResolutionCase.tenant_id==t)).all()
        entries=s.scalars(select(JournalEntry).where(JournalEntry.tenant_id==t)).all()
        currencies={}
        for o in orders: currencies.setdefault(o.currency,{"gross_order_value":Decimal("0"),"order_count":0}) ; currencies[o.currency]["gross_order_value"]+=Decimal(str(o.amount)); currencies[o.currency]["order_count"]+=1
        for c in costs:
            row=next((o for o in orders if o.id==c.order_id),None)
            if row: currencies.setdefault(row.currency,{"gross_order_value":Decimal("0"),"order_count":0}).setdefault("recorded_costs",Decimal("0")); currencies[row.currency]["recorded_costs"]+=sum(Decimal(str(getattr(c,k) or 0)) for k in ("cogs","shipping_out","payment_fee","packaging","other_cost"))
        return {"order_count":len(orders),"case_count":len(cases),"open_cases":sum(x.status not in {"CLOSED","CANCELLED"} for x in cases),"cost_coverage":len(costs),"currencies":{c:{k:str(v) for k,v in vals.items()} for c,vals in currencies.items()},"journal_entries":len(entries),"warning":"Currency totals are separated; estimated and realized outcomes are never combined."}

@router.put("/orders/{order_id}/costs")
def put_costs(order_id:str,body:dict,p=Depends(principal)):
    role(p,{"OWNER","ADMIN","OPERATOR"})
    keys=("cogs","shipping_out","payment_fee","packaging","other_cost")
    vals={k:dec(body.get(k,0),k) for k in keys}
    with tenant_session(p["tenant_id"]) as s:
        order=s.scalar(select(TenantOrder).where(TenantOrder.id==order_id,TenantOrder.tenant_id==p["tenant_id"]))
        if not order: raise HTTPException(404,"Order not found")
        row=s.scalar(select(OrderCost).where(OrderCost.tenant_id==p["tenant_id"],OrderCost.order_id==order_id))
        if row is None:
            row=OrderCost(id=str(uuid.uuid4()),tenant_id=p["tenant_id"],order_id=order_id,updated_by=p["user_id"]);s.add(row)
        for k,v in vals.items(): setattr(row,k,v)
        row.updated_by=p["user_id"];row.updated_at=utcnow()
        audit(s,p,"ORDER_COSTS_UPDATED","ORDER",order_id,{k:str(v) for k,v in vals.items()})
    return {"order_id":order_id,"costs":{k:str(v) for k,v in vals.items()},"source":"MERCHANT_ENTERED"}

@router.post("/cases")
def create_case(body:dict,p=Depends(principal)):
    role(p,{"OWNER","ADMIN","OPERATOR"})
    kind=str(body.get("case_type","")).upper()
    if kind not in {"CANCELLATION","RETURN","REFUND","EXCHANGE"}: raise HTTPException(400,"case_type must be CANCELLATION, RETURN, REFUND or EXCHANGE")
    reason=str(body.get("reason","")).strip()
    if not 5<=len(reason)<=2000: raise HTTPException(400,"reason must contain 5–2000 characters")
    oid=str(body.get("order_id",""))
    requested=dec(body.get("requested_amount",0),"requested_amount")
    estimated=dec(body.get("estimated_loss",0),"estimated_loss")
    recovery=dec(body.get("recoverable_inventory_estimate",0),"recoverable_inventory_estimate")
    with tenant_session(p["tenant_id"]) as s:
        order=s.scalar(select(TenantOrder).where(TenantOrder.id==oid,TenantOrder.tenant_id==p["tenant_id"]))
        if not order: raise HTTPException(404,"Order not found in this workspace")
        payment=str(order.payment_status or "").upper()
        eligibility={"eligible":True,"reason":"Order exists in this workspace; manual policy review still required."}
        if kind=="CANCELLATION" and payment in {"CAPTURED","COMPLETED","PAID","PARTIALLY_REFUNDED","REFUNDED","SHIPPED","DELIVERED"}:
            eligibility={"eligible":False,"reason":"Payment is captured or fulfilment has progressed. Cancellation is blocked; assess return/refund instead. No payment reversal was attempted."}
        if kind=="CANCELLATION" and payment in {"CANCELLED","VOIDED"}:
            eligibility={"eligible":False,"reason":"Order is already cancelled or voided."}
        if kind=="REFUND" and requested<=0: raise HTTPException(400,"A positive requested_amount is required for refund cases")
        if kind=="EXCHANGE" and not body.get("return_reason_code"): raise HTTPException(400,"return_reason_code is required for exchange cases")
        if not eligibility["eligible"]: raise HTTPException(409,eligibility["reason"])
        cluster=body.get("complaint_cluster_id")
        if cluster:
            exists=s.scalar(select(TenantReview.id).where(
                TenantReview.tenant_id==p["tenant_id"],
                TenantReview.order_id==oid,
                TenantReview.complaint_cluster_id==str(cluster)))
            if not exists: raise HTTPException(400,"Complaint cluster is not linked to a review for this order in this workspace")
        row=ResolutionCase(id=str(uuid.uuid4()),tenant_id=p["tenant_id"],order_id=oid,case_type=kind,status="OPEN",reason=reason,complaint_cluster_id=str(cluster) if cluster else None,requested_amount=requested,estimated_loss=estimated,recoverable_inventory_estimate=recovery,return_reason_code=str(body.get("return_reason_code") or "") or None,created_by=p["user_id"])
        s.add(row);audit(s,p,"RESOLUTION_CASE_CREATED","FINANCIAL_CASE",row.id,{"order_id":oid,"case_type":kind,"complaint_cluster_id":cluster,"eligibility":eligibility})
    return {"id":row.id,"status":row.status,"eligibility":eligibility,"payment_action":"NONE","note":"Case recorded only. Provider payment actions require the separate financial approval workflow."}

@router.patch("/cases/{case_id}")
def update_case(case_id:str,body:dict,p=Depends(principal)):
    role(p,{"OWNER","ADMIN","OPERATOR"})
    allowed={"OPEN":{"UNDER_REVIEW","CANCELLED"},"UNDER_REVIEW":{"AUTHORIZED","REJECTED","CANCELLED"},"AUTHORIZED":{"IN_PROGRESS","CANCELLED"},"IN_PROGRESS":{"FULFILMENT_PENDING","COMPLETED","CANCELLED"},"FULFILMENT_PENDING":{"COMPLETED","CANCELLED"}}
    status=str(body.get("status","")).upper()
    with tenant_session(p["tenant_id"]) as s:
        row=s.scalar(select(ResolutionCase).where(ResolutionCase.id==case_id,ResolutionCase.tenant_id==p["tenant_id"]))
        if not row: raise HTTPException(404,"Case not found")
        if status and status!=row.status and status not in allowed.get(row.status,set()): raise HTTPException(409,f"Invalid transition {row.status} → {status}")
        if status=="AUTHORIZED":
            role(p,{"OWNER","ADMIN"})
            if p["user_id"]==row.created_by: raise HTTPException(403,"A different OWNER/ADMIN must authorize this case")
        if status=="COMPLETED":
            role(p,{"OWNER","ADMIN"})
            if len(str(body.get("evidence_reference","")).strip())<4: raise HTTPException(400,"evidence_reference is required to complete a case")
            if row.case_type=="EXCHANGE" and not (body.get("exchange_reference") or row.exchange_reference): raise HTTPException(400,"exchange_reference is required to complete an exchange")
        if status: row.status=status
        if "provider_reference" in body: row.provider_reference=str(body["provider_reference"])[:128]
        if "exchange_reference" in body: row.exchange_reference=str(body["exchange_reference"])[:128]
        # Actual financial values can only be entered by OWNER/ADMIN and must be evidence-backed.
        if "realized_loss" in body or "recovered_inventory_actual" in body:
            role(p,{"OWNER","ADMIN"})
            evidence=str(body.get("evidence_reference","")).strip()
            if len(evidence)<4: raise HTTPException(400,"evidence_reference is required for realized values")
            if "realized_loss" in body: row.realized_loss=dec(body["realized_loss"],"realized_loss")
            if "recovered_inventory_actual" in body: row.recovered_inventory_actual=dec(body["recovered_inventory_actual"],"recovered_inventory_actual")
        row.updated_at=utcnow()
        audit(s,p,"RESOLUTION_CASE_UPDATED","FINANCIAL_CASE",row.id,{"status":row.status,"provider_reference":row.provider_reference,"exchange_reference":row.exchange_reference})
    return case_dict(row)

@router.get("/orders/{order_id}/cancellation-assessment")
def cancellation_assessment(order_id:str,p=Depends(principal)):
    with tenant_session(p["tenant_id"]) as s:
        order=s.scalar(select(TenantOrder).where(TenantOrder.id==order_id,TenantOrder.tenant_id==p["tenant_id"]))
        if not order: raise HTTPException(404,"Order not found")
        payment=str(order.payment_status or "").upper()
        blocked={"CAPTURED","COMPLETED","PAID","PARTIALLY_REFUNDED","REFUNDED","SHIPPED","DELIVERED","CANCELLED","VOIDED"}
        eligible=payment not in blocked
        return {"order_id":order_id,"payment_status":payment,"cancellation_eligible":eligible,
          "payment_reversal_required":payment in {"AUTHORIZED","AUTHORISED","CAPTURED","COMPLETED","PAID"},
          "provider_action":"NONE","reason":"Order is not yet paid or fulfilled; merchant cancellation policy still applies." if eligible else "Payment or fulfilment has progressed; do not mark cancelled. Use return/refund assessment and the provider's separately authorized workflow.",
          "note":"This endpoint assesses eligibility only; it does not void an authorization, reverse a capture, or mutate the order."}

@router.post("/cases/{case_id}/refund-approval")
def create_refund_approval_from_case(case_id:str,p=Depends(principal)):
    role(p,{"OWNER","ADMIN","OPERATOR"})
    from .financial_controls import approval_digest
    with tenant_session(p["tenant_id"]) as s:
        case=s.scalar(select(ResolutionCase).where(ResolutionCase.id==case_id,ResolutionCase.tenant_id==p["tenant_id"]))
        if not case: raise HTTPException(404,"Case not found")
        if case.case_type not in {"REFUND","RETURN"}: raise HTTPException(409,"Only refund or return cases can request a refund")
        order=s.scalar(select(TenantOrder).where(TenantOrder.id==case.order_id,TenantOrder.tenant_id==p["tenant_id"]))
        if not order or not order.capture_id: raise HTTPException(409,"A provider capture ID is not recorded for this order")
        amount=Decimal(str(case.requested_amount))
        if amount<=0: raise HTTPException(400,"Case requested_amount must be positive")
        key=("case-"+case.id.replace("-",""))[:128]
        old=s.scalar(select(FinancialApprovalRequest).where(FinancialApprovalRequest.tenant_id==p["tenant_id"],FinancialApprovalRequest.request_key==key))
        if old: return {"approval_id":old.id,"status":old.status,"duplicate":True}
        reason=f"Resolution case {case.id}: {case.reason}"[:1000]
        digest=approval_digest(tenant_id=p["tenant_id"],capture_id=order.capture_id,amount=f"{amount:.2f}",currency=order.currency,reason=reason)
        row=FinancialApprovalRequest(id=str(uuid.uuid4()),tenant_id=p["tenant_id"],request_key=key,action="REFUND",capture_id=order.capture_id,amount=f"{amount:.2f}",currency=order.currency,reason=reason,policy_digest=digest,requester_id=p["user_id"],status="PENDING_RECONCILIATION")
        s.add(row);audit(s,p,"REFUND_APPROVAL_REQUESTED","FINANCIAL_CASE",case.id,{"approval_id":row.id,"amount":str(amount),"currency":order.currency})
    return {"approval_id":row.id,"status":row.status,"execution_authorized":False,"note":"Created a linked request in the existing PayPal approval workflow. Canonical provider reconciliation and independent approval are still required."}

@router.post("/cases/{case_id}/dispositions")
def add_disposition(case_id:str,body:dict,p=Depends(principal)):
    role(p,{"OWNER","ADMIN","OPERATOR"})
    disposition=str(body.get("disposition","")).upper()
    allowed={"RESTOCK","OPEN_BOX","REFURBISH","RETURN_TO_SUPPLIER","WRITE_OFF","INSPECT","REPAIR","REPACKAGE","DISCOUNT_RESALE","QUARANTINE","DISPOSE"}
    if disposition not in allowed: raise HTTPException(400,"Unsupported disposition")
    qty=int(body.get("quantity",1))
    if qty<1 or qty>100000: raise HTTPException(400,"quantity must be between 1 and 100000")
    estimate=dec(body.get("estimated_recovery",0),"estimated_recovery")
    actual=body.get("realized_recovery")
    if actual is not None:
        role(p,{"OWNER","ADMIN"})
        if len(str(body.get("evidence_reference","")).strip())<4: raise HTTPException(400,"evidence_reference is required for realized inventory recovery")
    with tenant_session(p["tenant_id"]) as s:
        case=s.scalar(select(ResolutionCase).where(ResolutionCase.id==case_id,ResolutionCase.tenant_id==p["tenant_id"]))
        if not case: raise HTTPException(404,"Case not found")
        row=InventoryDisposition(id=str(uuid.uuid4()),tenant_id=p["tenant_id"],case_id=case_id,sku=str(body.get("sku") or "")[:100] or None,quantity=qty,disposition=disposition,estimated_recovery=estimate,realized_recovery=dec(actual,"realized_recovery") if actual is not None else None,warehouse_reference=str(body.get("warehouse_reference") or "")[:128] or None,note=str(body.get("note") or "")[:2000] or None,created_by=p["user_id"])
        s.add(row);audit(s,p,"INVENTORY_DISPOSITION_RECORDED","INVENTORY",row.id,{"case_id":case_id,"disposition":disposition,"quantity":qty,"warehouse_reference":row.warehouse_reference})
    return {"id":row.id,"disposition":disposition,"inventory_mutated":False,"note":"Disposition instruction recorded; stock is not changed without a connected warehouse/inventory adapter."}


def _llm_advice(features:dict):
    """Optional LLM interpretation. Off unless MERCHANTOS_LLM_ENABLED=true and OPENAI_API_KEY set.
    Receives only non-identifying structured features (no complaint text, names or IDs).
    Output is constrained to an enum and can never override a deterministic HOLD/REJECT. Never moves money."""
    if os.getenv("MERCHANTOS_LLM_ENABLED","").lower()!="true" or not os.getenv("OPENAI_API_KEY"): return None
    try:
        import json, requests
        model=os.getenv("MERCHANTOS_LLM_MODEL","gpt-4o-mini")
        base=os.getenv("OPENAI_BASE_URL","https://api.openai.com/v1").rstrip("/")
        r=requests.post(base+"/chat/completions",headers={"Authorization":"Bearer "+os.environ["OPENAI_API_KEY"]},timeout=15,json={"model":model,"temperature":0,"response_format":{"type":"json_object"},"messages":[{"role":"system","content":"You advise a merchant on a return/refund/exchange/cancellation case using only the structured features given. Reply as JSON: {\"recommendation\":\"APPROVE|REJECT|EXCHANGE\",\"reasons\":[up to 3 short strings]}. You are advisory only."},{"role":"user","content":json.dumps(features)}]})
        r.raise_for_status()
        data=json.loads(r.json()["choices"][0]["message"]["content"])
        rec=str(data.get("recommendation","")).upper()
        if rec not in {"APPROVE","REJECT","EXCHANGE"}: return None
        return {"recommendation":rec,"reasons":[str(x)[:200] for x in (data.get("reasons") or [])[:3]],"model":model}
    except Exception:
        return None

def _grid_signals(row,order,evidence_count:int)->dict:
    """Grid-level computed signals from stored order/fulfilment facts only.
    Unknown facts are reported as UNKNOWN, never assumed eligible."""
    requested=Decimal(str(row.requested_amount or 0))
    captured=Decimal(str(order.amount)) if order else None
    window=int(os.getenv("MERCHANTOS_RETURN_WINDOW_DAYS","7"))
    failed=[]; unknown=[]
    if row.case_type in {"RETURN","REFUND"} and captured is not None and requested>captured: failed.append("REFUND_CAP")
    if row.case_type in {"RETURN","REFUND","EXCHANGE"}:
        d=getattr(order,"delivered_at",None) if order else None
        if d is None: unknown.append("RETURN_WINDOW")
        else:
            if d.tzinfo is None: d=d.replace(tzinfo=timezone.utc)
            if (utcnow()-d).days>window: failed.append("RETURN_WINDOW")
    if row.case_type in {"RETURN","EXCHANGE"}:
        h=getattr(order,"hygiene_item",None) if order else None
        if h is True: failed.append("OPENED_HYGIENE_ITEM")
    if row.case_type=="CANCELLATION":
        sh=getattr(order,"shipped_at",None) if order else None
        if sh is not None: failed.append("CANCEL_BEFORE_SHIPPING")
    if failed: policy="NOT_ELIGIBLE: "+", ".join(failed)
    elif unknown: policy="UNKNOWN: delivery date missing ("+", ".join(unknown)+")"
    else: policy="ELIGIBLE"
    if not evidence_count or failed: ai="HOLD_FOR_EVIDENCE" if not evidence_count else "REJECT_REVIEW"
    elif row.case_type=="EXCHANGE": ai="EXCHANGE_REVIEW"
    elif row.case_type in {"RETURN","REFUND"}: ai="APPROVE_REVIEW"
    else: ai="REVIEW"
    est=Decimal(str(row.estimated_loss or 0)); rec=Decimal(str(row.recoverable_inventory_estimate or 0))
    return {"policy_result":policy,"ai_suggestion":ai,"ai_source":"computed_rules","net_result":str((rec-est).quantize(Decimal("0.01"))),"net_result_basis":"ESTIMATE: recoverable inventory estimate minus estimated loss (merchant-entered)"}

@router.put("/orders/{order_id}/fulfilment")
def put_fulfilment(order_id:str,body:dict,p=Depends(principal)):
    """Record delivery/shipping/hygiene facts used by the policy engine. Audited; merchant-supplied."""
    role(p,{"OWNER","ADMIN","OPERATOR"})
    def parse(k):
        v=body.get(k)
        if v in (None,""): return None
        try:
            d=datetime.fromisoformat(str(v).replace("Z","+00:00"))
        except ValueError: raise HTTPException(400,f"{k} must be an ISO-8601 date/time")
        return d if d.tzinfo else d.replace(tzinfo=timezone.utc)
    delivered=parse("delivered_at"); shipped=parse("shipped_at")
    hyg=body.get("hygiene_item")
    if hyg is not None and not isinstance(hyg,bool): raise HTTPException(400,"hygiene_item must be true/false")
    t=p["tenant_id"]
    with tenant_session(t) as s:
        o=s.scalar(select(TenantOrder).where(TenantOrder.id==order_id,TenantOrder.tenant_id==t))
        if not o: raise HTTPException(404,"Order not found")
        if "delivered_at" in body: o.delivered_at=delivered
        if "shipped_at" in body: o.shipped_at=shipped
        if "hygiene_item" in body: o.hygiene_item=hyg
        audit(s,p,"ORDER_FULFILMENT_FACTS_RECORDED","ORDER",order_id,{"delivered_at":str(delivered) if delivered else None,"shipped_at":str(shipped) if shipped else None,"hygiene_item":hyg,"source":"MERCHANT_SUPPLIED"})
        return {"order_id":order_id,"delivered_at":delivered.isoformat() if delivered else None,"shipped_at":shipped.isoformat() if shipped else None,"hygiene_item":hyg,"source":"MERCHANT_SUPPLIED"}

@router.get("/cases")
def list_cases(p=Depends(principal)):
    t=p["tenant_id"]
    with tenant_session(t) as s:
        rows=s.scalars(select(ResolutionCase).where(ResolutionCase.tenant_id==t).order_by(ResolutionCase.created_at.desc()).limit(500)).all()
        orders={o.id:o for o in s.scalars(select(TenantOrder).where(TenantOrder.tenant_id==t)).all()}
        case_ids=[r.id for r in rows]
        evidence_counts={}
        decision_events={}
        if case_ids:
            events=s.scalars(select(FinancialEvent).where(
                FinancialEvent.tenant_id==t,
                FinancialEvent.case_id.in_(case_ids),
                FinancialEvent.event_type.in_(("EVIDENCE_UPLOADED","HUMAN_APPROVAL_PROPOSED","HUMAN_CASE_REJECTED"))
            ).order_by(FinancialEvent.created_at.desc())).all()
            for event in events:
                if event.event_type=="EVIDENCE_UPLOADED":
                    evidence_counts[event.case_id]=evidence_counts.get(event.case_id,0)+1
                else:
                    decision_events.setdefault(event.case_id,event)
        output=[]
        for row in rows:
            order=orders.get(row.order_id)
            event=decision_events.get(row.id)
            decision=(event.payload.get("decision") if event else ("REJECT" if row.status=="REJECTED" else "PENDING"))
            output.append({**case_dict(row),"customer":(order.customer_name or order.customer_id or "Unknown") if order else "Unknown","product":order.product if order else None,"batch":order.batch if order else None,"amount":str(order.amount) if order else str(row.requested_amount),"currency":order.currency if order else None,"evidence_count":evidence_counts.get(row.id,0),"decision":decision,"decided_by":event.actor_id if event else None,**_grid_signals(row,order,evidence_counts.get(row.id,0))})
        return output

@router.get("/cases/{case_id}/events")
def case_events(case_id:str,p=Depends(principal)):
    with tenant_session(p["tenant_id"]) as s:
        case=s.scalar(select(ResolutionCase.id).where(ResolutionCase.id==case_id,ResolutionCase.tenant_id==p["tenant_id"]))
        if not case: raise HTTPException(404,"Case not found")
        rows=s.scalars(select(FinancialEvent).where(FinancialEvent.tenant_id==p["tenant_id"],FinancialEvent.case_id==case_id).order_by(FinancialEvent.created_at)).all()
        return [{"id":x.id,"event_type":x.event_type,"payload":x.payload,"created_at":x.created_at.isoformat()} for x in rows]

@router.post("/journal")
def post_journal(body:dict,p=Depends(principal)):
    role(p,{"OWNER","ADMIN","ACCOUNTANT"})
    currency=str(body.get("currency","")).upper()
    if len(currency)!=3 or not currency.isalpha(): raise HTTPException(400,"currency must be a three-letter code")
    key=str(body.get("idempotency_key","")).strip()
    if not 8<=len(key)<=128: raise HTTPException(400,"idempotency_key must be 8–128 characters")
    lines=body.get("lines")
    if not isinstance(lines,list) or len(lines)<2 or len(lines)>50: raise HTTPException(400,"At least two journal lines are required")
    normalized=[];debits=Decimal("0");credits=Decimal("0")
    for line in lines:
        account=str(line.get("account","")).strip()
        if not account or len(account)>100: raise HTTPException(400,"Each journal line requires an account")
        debit=dec(line.get("debit",0),"debit");credit=dec(line.get("credit",0),"credit")
        if (debit>0)==(credit>0): raise HTTPException(400,"Each line must have either a positive debit or a positive credit")
        debits+=debit;credits+=credit
        normalized.append({"account":account,"debit":str(debit),"credit":str(credit)})
    if debits<=0 or debits!=credits: raise HTTPException(409,"Journal is not balanced; total debits must equal total credits")
    with tenant_session(p["tenant_id"]) as s:
        old=s.scalar(select(JournalEntry).where(JournalEntry.tenant_id==p["tenant_id"],JournalEntry.idempotency_key==key))
        if old: return {"id":old.id,"duplicate":True,"currency":old.currency,"lines":old.lines}
        row=JournalEntry(id=str(uuid.uuid4()),tenant_id=p["tenant_id"],idempotency_key=key,source_type=str(body.get("source_type","MANUAL"))[:40],source_id=str(body.get("source_id",""))[:128],currency=currency,description=str(body.get("description",""))[:1000],lines=normalized,posted_by=p["user_id"])
        s.add(row);audit(s,p,"JOURNAL_POSTED","JOURNAL",row.id,{"currency":currency,"debits":str(debits),"credits":str(credits)})
    return {"id":row.id,"posted":True,"balanced":True,"currency":currency,"debits":str(debits),"credits":str(credits)}

@router.put("/reviews/{review_id}/cluster")
def link_review_cluster(review_id:str,body:dict,p=Depends(principal)):
    role(p,{"OWNER","ADMIN","OPERATOR"})
    cluster=str(body.get("complaint_cluster_id","")).strip()
    if not cluster or len(cluster)>100: raise HTTPException(400,"complaint_cluster_id is required")
    with tenant_session(p["tenant_id"]) as s:
        review=s.scalar(select(TenantReview).where(TenantReview.id==review_id,TenantReview.tenant_id==p["tenant_id"]))
        if not review: raise HTTPException(404,"Review not found")
        review.complaint_cluster_id=cluster
        audit(s,p,"REVIEW_CLUSTER_LINKED","REVIEW",review_id,{"complaint_cluster_id":cluster,"source":"MERCHANT_CONFIRMED"})
    return {"review_id":review_id,"complaint_cluster_id":cluster,"source":"MERCHANT_CONFIRMED"}

@router.post("/complaint-clusters/run")
def run_tenant_complaint_clustering(body: dict | None = None, p=Depends(principal)):
    """Cluster and persist deterministic cluster IDs only within the caller's tenant."""
    body = body or {}
    try:
        threshold = float(body.get("threshold", 0.15))
    except (TypeError, ValueError):
        raise HTTPException(400, "threshold must be a number between 0 and 1")
    if not 0.0 <= threshold <= 1.0:
        raise HTTPException(400, "threshold must be between 0 and 1")
    role(p, {"OWNER", "ADMIN", "OPERATOR", "ANALYST"})
    t = p["tenant_id"]
    with tenant_session(t) as s:
        reviews = s.scalars(select(TenantReview).where(
            TenantReview.tenant_id == t
        ).order_by(TenantReview.created_at, TenantReview.id).limit(5000)).all()
        rows = [{"id": r.id, "text": r.text, "rating": r.rating,
                 "order_id": r.order_id, "product": r.product} for r in reviews]
        from .tenant_clustering import cluster_reviews
        result = cluster_reviews(rows, threshold=threshold)
        assignments = {review_id: cluster["cluster_id"] for cluster in result["clusters"] for review_id in cluster["review_ids"]}
        for review in reviews:
            review.complaint_cluster_id = assignments.get(review.id)
        audit_detail = {"review_count": result["review_count"], "cluster_count": len(result["clusters"]), "method": result["method"], "threshold": threshold}
        latest = s.scalar(select(TenantAuditEvent).where(
            TenantAuditEvent.tenant_id == t,
            TenantAuditEvent.event == "TENANT_COMPLAINTS_CLUSTERED",
        ).order_by(TenantAuditEvent.created_at.desc()).limit(1))
        # A repeated identical clustering request is idempotent in the audit
        # stream; only a changed result/configuration creates a new event.
        if not latest or latest.detail != audit_detail:
            audit(s, p, "TENANT_COMPLAINTS_CLUSTERED", "REVIEW_SET", t, audit_detail)
    result["scope"] = "authenticated_tenant_only"
    result["assignments_persisted"] = len(assignments)
    result["external_processing"] = "enabled_by_explicit_opt_in" if os.getenv("MERCHANTOS_ALLOW_EXTERNAL_REVIEW_PROCESSING", "false").lower() in {"1", "true", "yes"} else "disabled"
    return result


@router.get("/complaint-clusters")
def get_tenant_complaint_clusters(p=Depends(principal)):
    """Return persisted cluster summaries for the authenticated tenant only."""
    t = p["tenant_id"]
    with tenant_session(t) as s:
        reviews = s.scalars(select(TenantReview).where(
            TenantReview.tenant_id == t, TenantReview.complaint_cluster_id.is_not(None)
        ).order_by(TenantReview.created_at, TenantReview.id).limit(5000)).all()
        grouped = {}
        for review in reviews:
            group = grouped.setdefault(review.complaint_cluster_id, {"cluster_id": review.complaint_cluster_id, "count": 0, "review_ids": [], "examples": [], "ratings": []})
            group["count"] += 1
            group["review_ids"].append(review.id)
            if len(group["examples"]) < 3: group["examples"].append((review.text or "")[:240])
            if review.rating is not None: group["ratings"].append(int(review.rating))
        output = []
        for group in grouped.values():
            ratings = group.pop("ratings")
            group["average_rating"] = round(sum(ratings) / len(ratings), 2) if ratings else None
            output.append(group)
        latest_run = s.scalar(select(TenantAuditEvent).where(
            TenantAuditEvent.tenant_id == t,
            TenantAuditEvent.event == "TENANT_COMPLAINTS_CLUSTERED",
        ).order_by(TenantAuditEvent.created_at.desc()).limit(1))
        detail = latest_run.detail if latest_run and isinstance(latest_run.detail, dict) else {}
        return {"scope": "authenticated_tenant_only", "review_count": len(reviews),
                "clusters": sorted(output, key=lambda x: (-x["count"], x["cluster_id"])),
                "method": detail.get("method", "not_run"),
                "external_processing": "enabled_by_explicit_opt_in" if os.getenv("MERCHANTOS_ALLOW_EXTERNAL_REVIEW_PROCESSING", "false").lower() in {"1", "true", "yes"} else "disabled",
                "caveat": "Similarity groups are exploratory signals, not proof of a shared root cause."}


@router.get("/intelligence")
def intelligence(p=Depends(principal)):
    t=p["tenant_id"]
    with tenant_session(t) as s:
        cases=s.scalars(select(ResolutionCase).where(ResolutionCase.tenant_id==t)).all()
        reviews=s.scalars(select(TenantReview).where(TenantReview.tenant_id==t)).all()
        costs=s.scalars(select(OrderCost).where(OrderCost.tenant_id==t)).all()
        orders={o.id:o for o in s.scalars(select(TenantOrder).where(TenantOrder.tenant_id==t)).all()}
        by_cluster={}
        for c in cases:
            if c.complaint_cluster_id:
                b=by_cluster.setdefault(c.complaint_cluster_id,{"cases":0,"estimated_loss":Decimal("0"),"realized_loss":Decimal("0"),"realized_records":0})
                b["cases"]+=1;b["estimated_loss"]+=Decimal(str(c.estimated_loss or 0))
                if c.realized_loss is not None:b["realized_loss"]+=Decimal(str(c.realized_loss));b["realized_records"]+=1
        batch={}
        case_order_ids={c.order_id for c in cases}
        for c in cases:
            o=orders.get(c.order_id)
            if not o or not o.batch: continue
            b=batch.setdefault(o.batch,{"cases":0,"estimated_loss":Decimal("0"),"realized_loss":Decimal("0")})
            b["cases"]+=1;b["estimated_loss"]+=Decimal(str(c.estimated_loss or 0))
            if c.realized_loss is not None:b["realized_loss"]+=Decimal(str(c.realized_loss))
        batch_stats={}
        total_complaints=len(case_order_ids); total_orders=len(orders)
        for batch_name in {o.batch for o in orders.values() if o.batch}:
            in_batch=[o for o in orders.values() if o.batch==batch_name]
            out_batch=[o for o in orders.values() if o.batch!=batch_name]
            a=sum(o.id in case_order_ids for o in in_batch); b=len(in_batch)-a
            c=sum(o.id in case_order_ids for o in out_batch); d=len(out_batch)-c
            rate=a/len(in_batch) if in_batch else 0.0
            baseline=c/len(out_batch) if out_batch else 0.0
            lift=(rate/baseline) if baseline>0 else None
            batch_stats[batch_name]={"orders":len(in_batch),"complaint_orders":a,"complaint_rate":round(rate,4),"baseline_rate_excluding_batch":round(baseline,4),"lift":round(lift,4) if lift is not None else None,"fisher_exact_two_sided_p":round(fisher_exact_two_sided(a,b,c,d),6) if total_orders else 1.0,"interpretation":"correlation, not proven cause"}
        customer_counts={}
        for c in cases:
            o=orders.get(c.order_id)
            if o and o.customer_id: customer_counts[o.customer_id]=customer_counts.get(o.customer_id,0)+1
        repeat_returners=[{"customer_id":k,"case_count":v,"signal_only":True} for k,v in customer_counts.items() if v>1]
        cost_by_reason={}
        by_product={}
        by_week={}
        for c in cases:
            key=c.return_reason_code or "UNSPECIFIED"
            val=cost_by_reason.setdefault(key,{"case_count":0,"estimated_loss":Decimal("0"),"realized_loss":Decimal("0")})
            val["case_count"]+=1;val["estimated_loss"]+=Decimal(str(c.estimated_loss or 0))
            if c.realized_loss is not None: val["realized_loss"]+=Decimal(str(c.realized_loss))
            order=orders.get(c.order_id)
            product=(order.product if order and order.product else "UNSPECIFIED")
            pv=by_product.setdefault(product,{"case_count":0,"estimated_loss":Decimal("0"),"realized_loss":Decimal("0")})
            pv["case_count"]+=1;pv["estimated_loss"]+=Decimal(str(c.estimated_loss or 0))
            if c.realized_loss is not None: pv["realized_loss"]+=Decimal(str(c.realized_loss))
            week=(c.created_at.date().isocalendar() if c.created_at else None)
            week_key=f"{week.year}-W{week.week:02d}" if week else "UNKNOWN"
            wv=by_week.setdefault(week_key,{"case_count":0,"estimated_loss":Decimal("0"),"realized_loss":Decimal("0")})
            wv["case_count"]+=1;wv["estimated_loss"]+=Decimal(str(c.estimated_loss or 0))
            if c.realized_loss is not None: wv["realized_loss"]+=Decimal(str(c.realized_loss))
        # Transparent z-score signals on complaint-order rate, not an ML accuracy claim.
        def dimension_rates(key_fn):
            groups={}
            for order in orders.values():
                key=key_fn(order)
                if not key: continue
                row=groups.setdefault(str(key),{"orders":0,"complaint_orders":0})
                row["orders"]+=1
                if order.id in case_order_ids: row["complaint_orders"]+=1
            for row in groups.values(): row["rate"]=row["complaint_orders"]/row["orders"] if row["orders"] else 0.0
            values=[x["rate"] for x in groups.values()]
            avg=sum(values)/len(values) if values else 0.0
            variance=sum((x-avg)**2 for x in values)/len(values) if values else 0.0
            spread=variance**0.5
            for row in groups.values(): row["z_score"]=round((row["rate"]-avg)/spread,4) if spread>1e-12 else 0.0
            if len(groups)>=8:
                try:
                    from sklearn.ensemble import IsolationForest
                    _keys=list(groups); _X=[[groups[k]["rate"]] for k in _keys]
                    _sc=IsolationForest(n_estimators=100,random_state=0).fit(_X).score_samples(_X)
                    for _k,_v in zip(_keys,_sc): groups[_k]["isolation_forest_score"]=round(float(-_v),4)
                except Exception: pass
            return groups if len(groups)>=3 else {k:{**v,"z_score":None,"signal":"INSUFFICIENT_GROUPS"} for k,v in groups.items()}
        anomaly_signals={"customer":dimension_rates(lambda o:o.customer_id),"product":dimension_rates(lambda o:o.product),"batch":dimension_rates(lambda o:o.batch),"method":"descriptive complaint-rate z-score (min 3 groups) plus Isolation Forest score when 8+ groups; exploratory, not causal"}
        stringify=lambda table:{k:{a:(str(v) if isinstance(v,Decimal) else v) for a,v in b.items()} for k,b in table.items()}
        return {"case_count":len(cases),"linked_review_count":sum(1 for r in reviews if r.order_id in case_order_ids),"by_complaint_cluster":{k:{a:str(v) for a,v in b.items()} for k,b in by_cluster.items()},"by_batch":stringify(batch),"batch_statistics":batch_stats,"by_product":stringify(by_product),"by_week":stringify(by_week),"repeat_returners":repeat_returners,"cost_by_reason":stringify(cost_by_reason),"anomaly_signals":anomaly_signals,"limitations":"Associations are descriptive, not causal. Fisher exact p-values are exploratory; small samples and data completeness affect interpretation. Z-scores are descriptive signals, not proof of abuse. Only merchant-entered and evidence-backed realized amounts are counted as realized."}

@router.get("/reconciliation")
def reconciliation(p=Depends(principal)):
    t=p["tenant_id"]
    with tenant_session(t) as s:
        executions=s.scalars(select(FinancialExecution).where(FinancialExecution.tenant_id==t)).all()
        journals=s.scalars(select(JournalEntry).where(JournalEntry.tenant_id==t)).all()
        journal_sources={(j.source_type,j.source_id,j.currency) for j in journals}
        rows=[]
        for x in executions:
            approval=s.scalar(select(FinancialApprovalRequest).where(FinancialApprovalRequest.id==x.approval_id,FinancialApprovalRequest.tenant_id==t))
            if not approval: continue
            rows.append({"execution_id":x.id,"provider_status":x.provider_status or x.status,"amount":approval.amount,"currency":approval.currency,"provider_refund_id":x.provider_refund_id,"journal_linked":("PAYPAL_REFUND",x.id,approval.currency) in journal_sources,"reconciliation_status":"MATCHED" if ("PAYPAL_REFUND",x.id,approval.currency) in journal_sources else "MISSING_JOURNAL_ENTRY"})
        return {"items":rows,"matched":sum(x["journal_linked"] for x in rows),"unmatched":sum(not x["journal_linked"] for x in rows),"note":"This compares MerchantOS execution records with journal links. It is not a bank settlement reconciliation."}


@router.post("/policy/assess")
def policy_assess(body:dict,p=Depends(principal)):
    """Deterministic policy check. Facts are merchant-supplied and recorded in audit."""
    role(p,{"OWNER","ADMIN","OPERATOR"})
    kind=str(body.get("case_type","RETURN")).upper()
    if kind not in {"RETURN","REFUND","EXCHANGE","CANCELLATION"}: raise HTTPException(400,"Unsupported case_type")
    try: days=int(body.get("days_since_delivery",0)); captured=dec(body.get("captured_amount",0),"captured_amount"); requested=dec(body.get("requested_amount",0),"requested_amount")
    except (TypeError,ValueError): raise HTTPException(400,"Invalid policy facts")
    window=int(os.getenv("MERCHANTOS_RETURN_WINDOW_DAYS","7"))
    rules=[]
    if kind in {"RETURN","REFUND","EXCHANGE"} and days>window: rules.append({"rule":"RETURN_WINDOW","eligible":False,"detail":f"Request is {days} days after delivery; configured window is {window} days."})
    if kind=="EXCHANGE" and body.get("previous_exchange_for_order") is True: rules.append({"rule":"ONE_EXCHANGE_PER_ORDER","eligible":False,"detail":"An exchange is already recorded for this order."})
    if kind in {"RETURN","EXCHANGE"} and body.get("hygiene_item_opened") is True: rules.append({"rule":"OPENED_HYGIENE_ITEM","eligible":False,"detail":"Opened hygiene items are not returnable/exchangeable."})
    if kind in {"RETURN","REFUND"} and requested>captured: rules.append({"rule":"REFUND_CAP","eligible":False,"detail":"Requested refund exceeds captured amount."})
    if kind=="CANCELLATION" and body.get("shipped") is True: rules.append({"rule":"CANCEL_BEFORE_SHIPPING","eligible":False,"detail":"Cancellation is only allowed before shipping."})
    failed=[r for r in rules if not r["eligible"]]
    override=str(body.get("override_reason","")).strip()
    if failed and override and len(override) < 5:
        raise HTTPException(400,"override_reason must contain at least 5 characters")
    eligible=not failed or bool(override)
    if failed and override:
        with tenant_session(p["tenant_id"]) as s:
            audit(s,p,"POLICY_OVERRIDE_RECORDED","POLICY_ASSESSMENT",str(uuid.uuid4()),{"case_type":kind,"failed_rules":failed,"override_reason":override[:1000],"facts":{k:body.get(k) for k in ("days_since_delivery","captured_amount","requested_amount","previous_exchange_for_order","hygiene_item_opened","shipped")}})
    return {"eligible":eligible,"rules":rules,"failed_rules":failed,"override_reason":override or None,"decision":"OVERRIDDEN_BY_MERCHANT" if failed and override else ("INELIGIBLE" if failed else "ELIGIBLE"),"source":"DETERMINISTIC_POLICY_ENGINE","facts_disclosure":"Policy facts are supplied by the merchant; validate against order and fulfillment records before acting."}


@router.post("/financial-preview")
def financial_preview(body:dict,p=Depends(principal)):
    """Transparent estimate only; every input is identified as merchant supplied."""
    role(p,{"OWNER","ADMIN","OPERATOR","ACCOUNTANT"})
    cogs=dec(body.get("cogs",0),"cogs"); refund=dec(body.get("refund",0),"refund"); shipping=dec(body.get("return_shipping",0),"return_shipping"); handling=dec(body.get("handling",0),"handling"); fee=dec(body.get("payment_fee",0),"payment_fee"); repair=dec(body.get("repair_cost",0),"repair_cost"); writeoff=dec(body.get("write_off",0),"write_off")
    disposition=str(body.get("disposition","RESTOCK")).upper()
    def configured_rate(name,default):
        try: value=Decimal(os.getenv(name,default))
        except Exception: raise HTTPException(500,f"Invalid recovery rate configuration: {name}")
        if value<0 or value>1: raise HTTPException(500,f"Recovery rate must be between 0 and 1: {name}")
        return value
    rates={"RESTOCK":Decimal("1.00"),"OPEN_BOX":configured_rate("MERCHANTOS_OPEN_BOX_RECOVERY_RATE","0.70"),"REFURBISH":configured_rate("MERCHANTOS_REFURBISH_RECOVERY_RATE","0.60"),"RETURN_TO_SUPPLIER":Decimal("0.00"),"WRITE_OFF":Decimal("0.00")}
    if disposition not in rates: raise HTTPException(400,"Unsupported disposition")
    supplier_credit=dec(body.get("supplier_credit",0),"supplier_credit")
    recovered=supplier_credit if disposition=="RETURN_TO_SUPPLIER" else (cogs*rates[disposition])
    if disposition=="REFURBISH": recovered=max(Decimal("0"),recovered-repair)
    net=recovered-refund-shipping-handling-fee-writeoff
    return {"currency":str(body.get("currency","INR")).upper(),"disposition":disposition,"recovered_item_value":str(recovered.quantize(Decimal("0.01"))),"refund":str(refund),"return_shipping":str(shipping),"handling":str(handling),"payment_fee":str(fee),"write_off":str(writeoff),"net_recovery":str(net.quantize(Decimal("0.01"))),"margin_lost_vs_cogs":str(max(Decimal("0"),cogs-recovered+refund+shipping+handling+fee+writeoff).quantize(Decimal("0.01"))),"formula":"recovered item value - refund - return shipping - handling - payment fee - write-off","recovery_rate":str(rates[disposition]),"payment_fee_basis":"PayPal Merchant Fees terms: no fee is charged to make a refund, but fees originally paid to receive the payment are not returned. Enter the ORIGINAL payment fee as the lost-fee line. Terms are region-specific; confirm for your PayPal account/country.","source_disclosure":"All amounts are merchant-supplied estimates with the source disclosed here; this does not assert provider-confirmed status."}



@router.get("/cases/{case_id}/detail")
def case_detail(case_id: str, p=Depends(principal)):
    """Tenant-scoped case investigation bundle with transparent computed signals."""
    t=p["tenant_id"]
    with tenant_session(t) as s:
        case=s.scalar(select(ResolutionCase).where(ResolutionCase.id==case_id,ResolutionCase.tenant_id==t))
        if not case: raise HTTPException(404,"Case not found")
        order=s.scalar(select(TenantOrder).where(TenantOrder.id==case.order_id,TenantOrder.tenant_id==t))
        if not order: raise HTTPException(404,"Order not found")
        reviews=s.scalars(select(TenantReview).where(TenantReview.tenant_id==t,TenantReview.order_id==case.order_id).order_by(TenantReview.created_at.desc()).limit(10)).all()
        case_events=s.scalars(select(FinancialEvent).where(FinancialEvent.tenant_id==t,FinancialEvent.case_id==case_id).order_by(FinancialEvent.created_at.desc()).limit(100)).all()
        evidence_ids=[str(ev.payload.get("evidence_id")) for ev in case_events if ev.event_type=="EVIDENCE_UPLOADED" and ev.payload.get("evidence_id")]
        evidence=s.scalars(select(TenantEvidence).where(TenantEvidence.tenant_id==t,TenantEvidence.id.in_(evidence_ids)).order_by(TenantEvidence.created_at.desc())).all() if evidence_ids else []
        dispositions=s.scalars(select(InventoryDisposition).where(InventoryDisposition.tenant_id==t,InventoryDisposition.case_id==case_id).order_by(InventoryDisposition.created_at.desc())).all()
        cost=s.scalar(select(OrderCost).where(OrderCost.tenant_id==t,OrderCost.order_id==case.order_id))
        related=s.scalars(select(ResolutionCase).where(ResolutionCase.tenant_id==t,ResolutionCase.order_id!=case.order_id)).all()
        same_batch=0; repeat_count=0
        all_orders={x.id:x for x in s.scalars(select(TenantOrder).where(TenantOrder.tenant_id==t)).all()}
        for other in related:
            other_order=all_orders.get(other.order_id)
            if other_order and order.batch and other_order.batch==order.batch: same_batch+=1
            if other_order and order.customer_id and other_order.customer_id==order.customer_id: repeat_count+=1
        events=case_events[:30]
        approval_key=("case-"+case.id.replace("-",""))[:128]
        approval=s.scalar(select(FinancialApprovalRequest).where(FinancialApprovalRequest.tenant_id==t,FinancialApprovalRequest.request_key==approval_key))
        execution=s.scalar(select(FinancialExecution).where(FinancialExecution.tenant_id==t,FinancialExecution.approval_id==approval.id)) if approval else None
        amount=Decimal(str(case.requested_amount or 0)); estimate=Decimal(str(case.estimated_loss or 0)); recovery=Decimal(str(case.recoverable_inventory_estimate or 0))
        # Deterministic heuristic, not an LLM and not a calibrated probability.
        reasons=[]; flags=[]
        if evidence: reasons.append(f"{len(evidence)} order-linked evidence item(s) are registered.")
        else: reasons.append("No order-linked evidence is registered; human decision should remain blocked.")
        if repeat_count: flags.append("REPEAT_RETURNER_SIGNAL")
        if same_batch: flags.append("SAME_BATCH_CASE_SIGNAL")
        if not evidence: flags.append("EVIDENCE_MISSING")
        mismatch=[e.id for e in evidence if e.order_id!=case.order_id or not str(e.integrity_status or "").startswith("SHA256_VERIFIED")]
        if mismatch: flags.append("EVIDENCE_MISMATCH")
        if case.case_type in {"RETURN","REFUND"} and amount>Decimal(str(order.amount)): flags.append("REQUEST_EXCEEDS_ORDER_AMOUNT")
        policy_result=_grid_signals(case,order,len(evidence))["policy_result"]
        if not evidence: recommendation="HOLD_FOR_EVIDENCE"
        elif policy_result.startswith("NOT_ELIGIBLE") or "REQUEST_EXCEEDS_ORDER_AMOUNT" in flags: recommendation="REJECT"
        elif "EVIDENCE_MISMATCH" in flags: recommendation="HOLD_FOR_EVIDENCE"
        elif case.case_type=="EXCHANGE": recommendation="EXCHANGE"
        elif case.case_type in {"RETURN","REFUND","CANCELLATION"}: recommendation="APPROVE"
        else: recommendation="REVIEW"
        checks=[("Evidence attached",bool(evidence)),("Policy rules not failed",not policy_result.startswith("NOT_ELIGIBLE")),("Policy facts known (delivery date etc.)",not policy_result.startswith("UNKNOWN")),("No evidence mismatch",not mismatch),("Not a repeat returner",not repeat_count),("No other cases from same batch",not same_batch)]
        passed=sum(1 for _,ok in checks if ok)
        strength="HIGH" if passed==len(checks) else ("MEDIUM" if passed>=len(checks)-2 else "LOW")
        reasons.append("Policy: "+policy_result)
        reasons+= [f"Check not passed: {name}" for name,ok in checks if not ok]
        expected={"approve":str((estimate-recovery).quantize(Decimal("0.01"))),"reject":str(estimate.quantize(Decimal("0.01"))),"exchange":str(max(Decimal("0"),estimate-recovery).quantize(Decimal("0.01")))}
        return {
            "case":case_dict(case),
            "order":{"id":order.id,"customer_id":order.customer_id,"customer_name":order.customer_name,"product":order.product,"batch":order.batch,"amount":str(order.amount),"currency":order.currency,"payment_status":order.payment_status,"created_at":order.created_at.isoformat() if order.created_at else None,"delivery_date":order.delivered_at.isoformat() if getattr(order,"delivered_at",None) else None,"shipped_at":order.shipped_at.isoformat() if getattr(order,"shipped_at",None) else None,"hygiene_item":getattr(order,"hygiene_item",None),"capture_id_present":bool(order.capture_id)},
            "complaints":[{"id":r.id,"message":r.text,"category":r.category,"severity":r.severity,"created_at":r.created_at.isoformat() if r.created_at else None} for r in reviews],
            "evidence":[{"id":e.id,"type":e.evidence_type,"description":e.description,"sha256":e.sha256,"integrity_status":e.integrity_status,"download_url":f"/api/v1/financial-lifecycle/evidence/{e.id}/download" if e.storage_key else None,"created_at":e.created_at.isoformat() if e.created_at else None} for e in evidence],
            "costs":({k:str(getattr(cost,k) or 0) for k in ("cogs","shipping_out","payment_fee","packaging","other_cost")} if cost else None),
            "dispositions":[{"id":d.id,"sku":d.sku,"quantity":d.quantity,"disposition":d.disposition,"estimated_recovery":str(d.estimated_recovery),"realized_recovery":str(d.realized_recovery) if d.realized_recovery is not None else None,"warehouse_reference":d.warehouse_reference,"note":d.note,"created_at":d.created_at.isoformat() if d.created_at else None} for d in dispositions],
            "signals":{"repeat_returner_case_count":repeat_count,"other_cases_same_batch":same_batch,"flags":flags},
            "computed_recommendation":(lambda llm:{"recommendation":(llm["recommendation"] if llm and recommendation not in {"HOLD_FOR_EVIDENCE","REJECT"} else recommendation),"mode":("llm_validated" if llm else "computed"),"model":(llm["model"] if llm else "computed_rules"),"confidence_label":"signal agreement (rule checks passed) — not a calibrated probability","signal_strength":strength,"checks_passed":f"{passed}/{len(checks)}","reasons":reasons+((["LLM: "+x for x in llm["reasons"]]) if llm else []),"expected_loss_estimates":expected,"expected_loss_math":[f"approve = estimated loss - recoverable inventory = {estimate} - {recovery} = {expected['approve']}",f"reject = estimated loss retained = {expected['reject']} (chargeback/dispute risk not modelled)",f"exchange = max(0, estimated loss - recoverable inventory) = {expected['exchange']}","All inputs are merchant-entered estimates."],"llm_advice":llm,"computed_recommendation":recommendation,"policy_result":policy_result,"validation":"Deterministic checks validate; an LLM cannot override HOLD_FOR_EVIDENCE or REJECT. Humans authorize; AI never moves money.","accuracy_claim":None})(_llm_advice({"case_type":case.case_type,"flags":flags,"evidence_count":len(evidence),"policy_result":policy_result,"repeat_cases":repeat_count,"same_batch_cases":same_batch,"requested_amount_vs_paid_ratio":str((amount/Decimal(str(order.amount))).quantize(Decimal("0.01"))) if Decimal(str(order.amount)) else None})),
            "events":[{"id":e.id,"type":e.event_type,"payload":e.payload,"created_at":e.created_at.isoformat() if e.created_at else None} for e in events],
            "paypal":{"approval_id":approval.id if approval else None,"approval_status":approval.status if approval else None,"refund_id":execution.provider_refund_id if execution else None,"provider_status":execution.provider_status if execution else None,"environment":execution.environment if execution else "not executed"},
            "disclosure":"Signals are decision support only. AI/computed logic never authorizes or executes a payment. Human approval and the existing PayPal control path remain mandatory."
        }

@router.post("/cases/{case_id}/evidence")
async def upload_case_evidence(
    case_id: str,
    evidence_type: str = Form(...),
    description: str = Form(...),
    file: UploadFile = File(...),
    p=Depends(principal),
):
    """Private tenant-scoped upload. Requires a persistent private disk path in deployment."""
    role(p,{"OWNER","ADMIN","OPERATOR"})
    allowed={"product_photo","courier_receipt","customer_screenshot","order_document","other"}
    if evidence_type not in allowed: raise HTTPException(400,"Unsupported evidence type")
    description=description.strip()
    if not 5<=len(description)<=1000: raise HTTPException(400,"Evidence description must contain 5–1000 characters")
    mime=(file.content_type or "").lower()
    if mime not in {"image/jpeg","image/png","application/pdf"}: raise HTTPException(400,"Only JPEG, PNG and PDF evidence is accepted")
    data=await file.read(5*1024*1024+1)
    validate_case_evidence_limits(0, len(data))
    # Validate file signatures instead of trusting the browser MIME header.
    valid=(mime=="image/jpeg" and data.startswith(b"\xff\xd8\xff")) or (mime=="image/png" and data.startswith(b"\x89PNG\r\n\x1a\n")) or (mime=="application/pdf" and data.startswith(b"%PDF-"))
    if not valid: raise HTTPException(400,"File signature does not match the declared content type")
    digest=hashlib.sha256(data).hexdigest()
    phash=perceptual_hash(data) if mime.startswith("image/") else None
    if mime.startswith("image/") and phash is None:
        raise HTTPException(400,"Image payload could not be decoded; upload a valid JPEG or PNG")
    storage_root=Path(os.getenv("MERCHANTOS_EVIDENCE_DIR",os.getenv("EVIDENCE_UPLOAD_DIR","/var/data/merchantos-evidence"))).resolve()
    try:
        storage_root.mkdir(parents=True,exist_ok=True)
        os.chmod(storage_root,0o700)
    except OSError: raise HTTPException(503,"Private evidence storage is unavailable; configure MERCHANTOS_EVIDENCE_DIR on a persistent private disk")
    suffix={"image/jpeg":".jpg","image/png":".png","application/pdf":".pdf"}[mime]
    storage_name=f"{uuid.uuid4().hex}{suffix}"
    t=p["tenant_id"]
    with tenant_session(t) as s:
        # Serialize uploads for this case on PostgreSQL so parallel requests cannot
        # race past the eight-file limit. Other dialects retain the transactional count.
        if s.bind is not None and s.bind.dialect.name == "postgresql":
            s.execute(text("SELECT pg_advisory_xact_lock(hashtext(:lock_key))"), {"lock_key": t + ":" + case_id})
        case=s.scalar(select(ResolutionCase).where(ResolutionCase.id==case_id,ResolutionCase.tenant_id==t))
        if not case: raise HTTPException(404,"Case not found")
        case_uploads=s.scalars(select(FinancialEvent).where(FinancialEvent.tenant_id==t,FinancialEvent.case_id==case_id,FinancialEvent.event_type=="EVIDENCE_UPLOADED")).all()
        enforce_evidence_capacity(len(case_uploads))
        duplicate=s.scalar(select(TenantEvidence).where(TenantEvidence.tenant_id==t,TenantEvidence.sha256==digest))
        if duplicate: raise HTTPException(409,f"Duplicate evidence file matches existing evidence {duplicate.id}")
        if phash:
            prior=s.scalars(select(FinancialEvent).where(FinancialEvent.tenant_id==t,FinancialEvent.event_type=="EVIDENCE_UPLOADED")).all()
            near=next((ev for ev in prior if ev.payload.get("perceptual_hash") and hamming_hash_distance(phash,ev.payload["perceptual_hash"])<=5),None)
            if near: raise HTTPException(409,"Photo is perceptually similar to previously uploaded evidence in this workspace")
        target=(storage_root/storage_name).resolve()
        if storage_root not in target.parents: raise HTTPException(400,"Invalid storage path")
        try:
            with target.open("xb") as handle: handle.write(data)
        except OSError: raise HTTPException(503,"Could not persist evidence to the configured private disk")
        row=TenantEvidence(id=str(uuid.uuid4()),tenant_id=t,order_id=case.order_id,evidence_type=evidence_type,description=description,storage_key=storage_name,sha256=digest,integrity_status="SHA256_VERIFIED")
        s.add(row)
        s.add(FinancialEvent(id=str(uuid.uuid4()),tenant_id=t,case_id=case_id,event_type="EVIDENCE_UPLOADED",actor_id=p["user_id"],payload={"evidence_id":row.id,"order_id":case.order_id,"sha256":digest,"perceptual_hash":phash,"mime_type":mime,"size_bytes":len(data)}))
        audit(s,p,"CASE_EVIDENCE_UPLOADED","FINANCIAL_CASE",case_id,{"evidence_id":row.id,"sha256":digest,"perceptual_hash":phash,"mime_type":mime,"size_bytes":len(data)})
    return {"id":row.id,"case_id":case_id,"evidence_type":evidence_type,"sha256":digest,"perceptual_hash":phash,"size_bytes":len(data),"integrity_status":"SHA256_VERIFIED","duplicate":False,"storage":"PRIVATE_DISK"}

@router.get("/evidence/{evidence_id}/download")
def download_case_evidence(evidence_id: str, p=Depends(principal)):
    """Serve private evidence only to an authenticated member of its tenant."""
    with tenant_session(p["tenant_id"]) as s:
        row=s.scalar(select(TenantEvidence).where(TenantEvidence.id==evidence_id,TenantEvidence.tenant_id==p["tenant_id"]))
        if not row or not row.storage_key: raise HTTPException(404,"Evidence file not found")
        root=Path(os.getenv("MERCHANTOS_EVIDENCE_DIR",os.getenv("EVIDENCE_UPLOAD_DIR","/var/data/merchantos-evidence"))).resolve()
        target=(root/row.storage_key).resolve()
        if root not in target.parents or not target.is_file(): raise HTTPException(404,"Evidence file is unavailable")
        media=mimetypes.guess_type(target.name)[0] or "application/octet-stream"
        return FileResponse(target,media_type=media,filename=f"evidence-{row.id}{target.suffix}")

@router.post("/cases/{case_id}/decision")
def record_case_decision(case_id: str, body: dict, p=Depends(principal)):
    """Record a human decision; approval never directly triggers provider money movement."""
    role(p,{"OWNER","ADMIN","OPERATOR"})
    decision=str(body.get("decision","")).upper()
    reason_code=str(body.get("reason_code","")).upper()
    note=str(body.get("decision_note","")).strip()
    other=str(body.get("other_reason","")).strip()
    allowed_reasons={"DAMAGED","WRONG_ITEM","LATE","POLICY_VIOLATION","SUSPECTED_ABUSE","OTHER"}
    if decision not in {"APPROVE","REJECT"}: raise HTTPException(400,"Decision must be APPROVE or REJECT")
    if reason_code not in allowed_reasons: raise HTTPException(400,"A valid reason code is required")
    if reason_code=="OTHER" and len(other)<5: raise HTTPException(400,"Other reason must contain at least 5 characters")
    if len(note)<5: raise HTTPException(400,"Decision note must contain at least 5 characters")
    t=p["tenant_id"]
    with tenant_session(t) as s:
        case=s.scalar(select(ResolutionCase).where(ResolutionCase.id==case_id,ResolutionCase.tenant_id==t))
        if not case: raise HTTPException(404,"Case not found")
        evidence_count=s.scalar(select(func.count(FinancialEvent.id)).where(FinancialEvent.tenant_id==t,FinancialEvent.case_id==case_id,FinancialEvent.event_type=="EVIDENCE_UPLOADED")) or 0
        if evidence_count<1: raise HTTPException(409,"At least one evidence item attached to this case is required before a decision")
        if case.status not in {"OPEN","UNDER_REVIEW"}: raise HTTPException(409,f"Case cannot be decided from status {case.status}")
        if decision=="APPROVE":
            # Proposal only. Existing separate PayPal reconciliation, independent approval and execution remain mandatory.
            if case.case_type not in {"RETURN","REFUND","EXCHANGE"}: raise HTTPException(409,"Cancellation is not authorized through this resolution decision endpoint")
            if case.case_type in {"RETURN","REFUND"}:
                order=s.scalar(select(TenantOrder).where(TenantOrder.id==case.order_id,TenantOrder.tenant_id==t))
                if not order or not order.capture_id: raise HTTPException(409,"No provider capture is linked. No refund request was created.")
                if case.requested_amount<=0 or case.requested_amount>Decimal(str(order.amount)): raise HTTPException(409,"Refund amount must be positive and cannot exceed the order amount")
            case.status="UNDER_REVIEW"
            event_type="HUMAN_APPROVAL_PROPOSED"
            result_note="Human proposal recorded only. For refunds, independent maker-checker approval, provider reconciliation and PayPal Sandbox execution remain mandatory. Exchange fulfilment requires a warehouse/commerce adapter. No payment or inventory action was attempted."
        else:
            case.status="REJECTED";event_type="HUMAN_CASE_REJECTED"
            result_note="Rejected. No payment-provider action was attempted."
        payload={"decision":decision,"reason_code":reason_code,"reason":other if reason_code=="OTHER" else reason_code,"decision_note":note[:2000],"evidence_count":int(evidence_count)}
        s.add(FinancialEvent(id=str(uuid.uuid4()),tenant_id=t,case_id=case_id,event_type=event_type,actor_id=p["user_id"],payload=payload))
        audit(s,p,event_type,"FINANCIAL_CASE",case_id,payload)
    return {"case_id":case_id,"decision":decision,"status":case.status,"payment_action":"NONE","note":result_note}


@router.post("/cases/{case_id}/run-workflow")
async def run_case_resolution_workflow(case_id: str, p=Depends(principal)):
    """Dispatch advisory analysis to Render Workflows and persist the run reference."""
    role(p,{"OWNER","ADMIN","OPERATOR","ANALYST"})
    slug=os.getenv("WORKFLOW_SERVICE_SLUG","").strip()
    if not slug or not os.getenv("RENDER_API_KEY"):
        raise HTTPException(503,"Render Workflows are not configured; set WORKFLOW_SERVICE_SLUG and RENDER_API_KEY")
    t=p["tenant_id"]
    with tenant_session(t) as s:
        case=s.scalar(select(ResolutionCase).where(ResolutionCase.id==case_id,ResolutionCase.tenant_id==t))
        if not case: raise HTTPException(404,"Case not found")
        order=s.scalar(select(TenantOrder).where(TenantOrder.id==case.order_id,TenantOrder.tenant_id==t))
        if not order: raise HTTPException(404,"Order not found")
        status=str(order.payment_status or "").upper()
        normalized_status="refunded" if status=="REFUNDED" else ("disputed" if status=="DISPUTED" else ("captured" if status in {"CAPTURED","COMPLETED","PAID","PARTIALLY_REFUNDED"} else "refund_requested"))
        transaction={"id":order.id,"customer":str(order.customer_name or order.customer_id or "unknown"),"product":str(order.product or "unknown"),"amount":float(order.amount),"status":normalized_status,"created_at":order.created_at.isoformat() if order.created_at else utcnow().isoformat()}
        prior=s.scalars(select(FinancialEvent).where(FinancialEvent.tenant_id==t,FinancialEvent.case_id==case_id).order_by(FinancialEvent.created_at.desc()).limit(100)).all()
        events=[{"event_type":x.event_type,"payload":x.payload,"created_at":x.created_at.isoformat() if x.created_at else None} for x in reversed(prior)]
    try:
        from render import RenderAsync
        run=await RenderAsync().workflows.start_task(f"{slug}/run_resolution_pipeline",[[transaction],events,100.0,500.0])
    except Exception as exc:
        raise HTTPException(502,f"Render Workflow dispatch failed ({type(exc).__name__}); no financial action was attempted")
    run_id=str(run.id)
    run_url=os.getenv("MERCHANTOS_WORKFLOW_RUN_URL_TEMPLATE","").replace("{run_id}",run_id) or None
    with tenant_session(t) as s:
        s.add(FinancialEvent(id=str(uuid.uuid4()),tenant_id=t,case_id=case_id,event_type="WORKFLOW_RUN_STARTED",actor_id=p["user_id"],payload={"run_id":run_id,"status":str(getattr(run,"status","QUEUED")),"url":run_url,"workflow":"run_resolution_pipeline"}))
        audit(s,p,"RESOLUTION_WORKFLOW_DISPATCHED","FINANCIAL_CASE",case_id,{"run_id":run_id,"workflow":"run_resolution_pipeline"})
    return {"case_id":case_id,"run_id":run_id,"status":str(getattr(run,"status","QUEUED")),"url":run_url,"financial_action":"NONE"}

@router.get("/proof")
def proof(p=Depends(principal)):
    """Authenticated, tenant-scoped release evidence; missing integrations stay explicit."""
    import os
    t=p["tenant_id"]
    from sqlalchemy import desc
    with tenant_session(t) as s:
        audits=s.scalars(select(TenantAuditEvent).where(TenantAuditEvent.tenant_id==t).order_by(TenantAuditEvent.created_at.desc()).limit(10)).all()
        executions=s.scalars(select(FinancialExecution).where(FinancialExecution.tenant_id==t).order_by(FinancialExecution.created_at.desc()).limit(1)).all()
        latest=executions[0] if executions else None
        workflow_event=s.scalar(select(FinancialEvent).where(FinancialEvent.tenant_id==t,FinancialEvent.event_type=="WORKFLOW_RUN_STARTED").order_by(FinancialEvent.created_at.desc()).limit(1))
        run_id=(workflow_event.payload.get("run_id") if workflow_event else None) or os.getenv("MERCHANTOS_LATEST_WORKFLOW_RUN_ID") or None
        run_url=(workflow_event.payload.get("url") if workflow_event else None) or os.getenv("MERCHANTOS_LATEST_WORKFLOW_RUN_URL") or None
        return {
            "environment": "Sandbox" if os.getenv("PAYPAL_MODE", "sandbox").lower()=="sandbox" else "Non-sandbox configuration",
            "data_disclosure": "Demo data may be present; verify each record source before relying on it.",
            "render": {"service": os.getenv("RENDER_SERVICE_NAME", "merchantos-api"), "commit": os.getenv("RENDER_GIT_COMMIT", os.getenv("GIT_COMMIT", "unknown")), "uptime_seconds": None},
            "latest_paypal_refund": ({"refund_id": latest.provider_refund_id, "status": latest.provider_status or latest.status, "environment": latest.environment} if latest else None),
            "latest_workflow": ({"run_id": run_id, "url": run_url} if run_id else None),
            "workflow_disclosure": "No workflow run ID is configured or recorded." if not run_id else "Workflow run reference supplied by deployment configuration; open the linked run to verify.",
            "audit": [{"actor_user_id": x.actor_user_id, "action": x.event, "entity_type": x.entity_type, "entity_id": x.entity_id, "detail": x.detail, "timestamp": x.created_at.isoformat() if x.created_at else None} for x in audits],
            "status_semantics": {"implemented": "source code exists", "verified": "automated or documented test evidence exists", "live": "deployment/provider behavior confirmed"},
        }
