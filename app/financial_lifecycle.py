"""Tenant-scoped MerchantOS financial lifecycle API.

This module records estimates separately from realized values. It never performs
payment-provider writes or inventory movements. PayPal money movement remains in
the existing approval/execution service; inventory execution requires an external
warehouse integration and is deliberately represented as an auditable instruction.
"""
from __future__ import annotations
import uuid
from datetime import datetime, timezone, timedelta
from decimal import Decimal, InvalidOperation
from typing import Any
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import String, Text, DateTime, Numeric, Integer, ForeignKey, UniqueConstraint, Index, JSON, select, func
from sqlalchemy.orm import Mapped, mapped_column
from .orm_base import Base
from . import auth as identity
from .tenant_db import tenant_session
from .domain_models import TenantOrder, TenantReview, TenantAuditEvent
from .completion_models import FinancialExecution, FinancialApprovalRequest

router=APIRouter(prefix="/api/v1/financial-lifecycle",tags=["financial-lifecycle"])
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
    allowed={"RESTOCK","INSPECT","REPAIR","REPACKAGE","DISCOUNT_RESALE","QUARANTINE","DISPOSE","WRITE_OFF"}
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

@router.get("/cases")
def list_cases(p=Depends(principal)):
    with tenant_session(p["tenant_id"]) as s:
        rows=s.scalars(select(ResolutionCase).where(ResolutionCase.tenant_id==p["tenant_id"]).order_by(ResolutionCase.created_at.desc()).limit(500)).all()
        return [case_dict(x) for x in rows]

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
        for c in cases:
            o=orders.get(c.order_id)
            if not o or not o.batch: continue
            b=batch.setdefault(o.batch,{"cases":0,"estimated_loss":Decimal("0"),"realized_loss":Decimal("0")})
            b["cases"]+=1;b["estimated_loss"]+=Decimal(str(c.estimated_loss or 0))
            if c.realized_loss is not None:b["realized_loss"]+=Decimal(str(c.realized_loss))
        return {"case_count":len(cases),"linked_review_count":sum(1 for r in reviews if r.order_id in {c.order_id for c in cases}),"by_complaint_cluster":{k:{a:str(v) for a,v in b.items()} for k,b in by_cluster.items()},"by_batch":{k:{a:str(v) for a,v in b.items()} for k,b in batch.items()},"limitations":"Associations are descriptive, not causal. Only merchant-entered and evidence-backed realized amounts are counted as realized."}

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
