"""Tenant-scoped public customer storefront and complaint intake (PayPal Sandbox only)."""
from __future__ import annotations
import hashlib, os, re, secrets, uuid
from contextlib import contextmanager
from datetime import datetime, timezone, timedelta
from decimal import Decimal, InvalidOperation
import requests
from fastapi import APIRouter, Depends, HTTPException, Form, File, UploadFile, Request
from pydantic import BaseModel, Field
from sqlalchemy import String, DateTime, JSON, ForeignKey, UniqueConstraint, select
from sqlalchemy.orm import Mapped, mapped_column
from .orm_base import Base
from .tenant_db import tenant_session
from .domain_models import TenantOrder, TenantReview, TenantAuditEvent, TenantEvidence
from .financial_lifecycle import ResolutionCase, FinancialEvent
from . import auth as identity
from .paypal_tenant import _connection, _oauth, _base

router = APIRouter(tags=["storefront"])
def now(): return datetime.now(timezone.utc)
def digest(token): return hashlib.sha256(token.encode()).hexdigest()

class StorefrontConfig(Base):
    __tablename__ = "merchant_storefronts"
    __table_args__ = (UniqueConstraint("tenant_id", name="uq_storefront_tenant"), UniqueConstraint("slug", name="uq_storefront_slug"))
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    slug: Mapped[str] = mapped_column(String(80), nullable=False)
    products: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    active: Mapped[bool] = mapped_column(default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, nullable=False)

class StorefrontOrderAccess(Base):
    __tablename__ = "storefront_order_access"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    order_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

def principal(p=Depends(identity.current_principal)):
    if not identity.AUTH_AVAILABLE: raise HTTPException(503, "Identity service unavailable")
    return p

def provider(method, url, bearer, payload=None, request_id=None):
    headers={"Authorization":"Bearer "+bearer,"Content-Type":"application/json"}
    if request_id: headers["PayPal-Request-Id"]=request_id
    try: r=requests.request(method,url,headers=headers,json=payload,timeout=25)
    except requests.RequestException: raise HTTPException(502,"Could not reach PayPal Sandbox.")
    if not r.ok: raise HTTPException(502,f"PayPal Sandbox request failed ({r.status_code}).")
    try: return r.json()
    except ValueError: raise HTTPException(502,"PayPal returned an invalid response.")

class CatalogBody(BaseModel):
    slug: str = Field(min_length=3,max_length=80,pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
    products: list[dict] = Field(min_length=1,max_length=30)

@router.post("/api/v1/storefront/setup")
def setup(body: CatalogBody,p=Depends(principal)):
    if p["role"] not in {"OWNER","ADMIN"}: raise HTTPException(403,"Owner/admin access required.")
    products=[]; ids=set()
    for x in body.products:
        pid=str(x.get("id","")).strip()[:50]; name=str(x.get("name","")).strip()[:120]
        currency=str(x.get("currency","USD")).upper()
        try: amount=Decimal(str(x.get("amount",""))).quantize(Decimal("0.01"))
        except (InvalidOperation,ValueError): raise HTTPException(400,"Invalid product price.")
        if not pid or pid in ids or not name or not amount.is_finite() or amount<=0 or len(currency)!=3 or not currency.isalpha():
            raise HTTPException(400,"Products require unique IDs, names, positive prices and ISO currencies.")
        ids.add(pid); products.append({"id":pid,"name":name,"description":str(x.get("description",""))[:400],"amount":str(amount),"currency":currency})
    with tenant_session(p["tenant_id"]) as s:
        row=s.scalar(select(StorefrontConfig).where(StorefrontConfig.tenant_id==p["tenant_id"]))
        if row: row.slug=body.slug; row.products=products; row.active=True
        else: s.add(StorefrontConfig(tenant_id=p["tenant_id"],slug=body.slug,products=products,active=True))
        s.add(TenantAuditEvent(id=str(uuid.uuid4()),tenant_id=p["tenant_id"],actor_user_id=p["user_id"],event="STOREFRONT_CONFIGURED",entity_type="STOREFRONT",entity_id=body.slug,detail={"product_count":len(products)}))
    return {"active":True,"slug":body.slug,"store_path":"/store/"+body.slug,"products":products}

@contextmanager
def store_scope(slug):
    from .auth_sqlalchemy import SessionLocal
    lookup=SessionLocal()
    try:
        row=lookup.scalar(select(StorefrontConfig).where(StorefrontConfig.slug==slug,StorefrontConfig.active.is_(True)))
        if not row: raise HTTPException(404,"Storefront not found.")
        tenant_id=row.tenant_id
    finally: lookup.close()
    with tenant_session(tenant_id) as s:
        row=s.scalar(select(StorefrontConfig).where(StorefrontConfig.slug==slug,StorefrontConfig.tenant_id==tenant_id,StorefrontConfig.active.is_(True)))
        if not row: raise HTTPException(404,"Storefront not found.")
        yield tenant_id,row

@router.get("/api/store/{slug}")
def get_store(slug:str):
    with store_scope(slug) as (_,row):
        return {"slug":row.slug,"products":row.products,"environment":"PAYPAL_SANDBOX"}

class CheckoutBody(BaseModel):
    product_id:str=Field(min_length=1,max_length=50)
    customer_name:str=Field(min_length=1,max_length=120)
    customer_email:str=Field(min_length=3,max_length=254)

@router.post("/api/store/{slug}/checkout")
def checkout(slug:str,body:CheckoutBody,request:Request):
    with store_scope(slug) as (tenant_id,catalog):
        product=next((x for x in catalog.products if x["id"]==body.product_id),None)
        if not product: raise HTTPException(404,"Product not found.")
        c=_connection(tenant_id); bearer=_oauth(c["client_id"],c["client_secret"],"sandbox")
        order_id="MOS-"+uuid.uuid4().hex[:18].upper(); customer_token=secrets.token_urlsafe(32)
        public_url=str(request.base_url).rstrip("/")
        paypal=provider("POST",_base("sandbox")+"/v2/checkout/orders",bearer,{
            "intent":"CAPTURE","purchase_units":[{"reference_id":order_id,"custom_id":order_id,"description":product["name"],
                "amount":{"currency_code":product["currency"],"value":product["amount"]}}],
            "application_context":{"brand_name":"MerchantOS Demo Store","user_action":"PAY_NOW",
                "return_url":public_url+"/store/complete?merchant_order_id="+order_id+"&access="+customer_token,
                "cancel_url":public_url+"/store/"+slug+"?cancelled=1"}})
        approval=next((x.get("href") for x in paypal.get("links",[]) if x.get("rel") in {"payer-action","approve"}),None)
        if not approval: raise HTTPException(502,"PayPal did not return an approval URL.")
        order=TenantOrder(id=order_id,tenant_id=tenant_id,customer_id=hashlib.sha256(body.customer_email.strip().lower().encode()).hexdigest()[:32],
            customer_name=body.customer_name.strip(),product=product["name"],amount=Decimal(product["amount"]),currency=product["currency"],
            paypal_order_id=paypal.get("id"),capture_id=None,payment_status="CREATED")
        with tenant_session(tenant_id) as s:
            s.add(order); s.add(StorefrontOrderAccess(tenant_id=tenant_id,order_id=order_id,token_hash=digest(customer_token),expires_at=now()+timedelta(days=30)))
            s.add(TenantAuditEvent(id=str(uuid.uuid4()),tenant_id=tenant_id,actor_user_id=None,event="STOREFRONT_CHECKOUT_CREATED",entity_type="ORDER",entity_id=order_id,detail={"paypal_order_id":paypal.get("id"),"amount":product["amount"],"currency":product["currency"]}))
        return {"merchant_order_id":order_id,"paypal_order_id":paypal.get("id"),"approval_url":approval,"access_token":customer_token,"amount":product["amount"],"currency":product["currency"]}

def grant(order_id,access):
    from .auth_sqlalchemy import SessionLocal
    with SessionLocal() as s:
        row=s.scalar(select(StorefrontOrderAccess).where(StorefrontOrderAccess.order_id==order_id,StorefrontOrderAccess.token_hash==digest(access),StorefrontOrderAccess.expires_at>now()))
        if not row: raise HTTPException(403,"Customer order link is invalid or expired.")
        return row.tenant_id

@router.post("/api/store/order/{order_id}/capture")
def capture(order_id:str,access:str):
    tenant_id=grant(order_id,access); c=_connection(tenant_id); bearer=_oauth(c["client_id"],c["client_secret"],"sandbox")
    with tenant_session(tenant_id) as s:
        order=s.scalar(select(TenantOrder).where(TenantOrder.id==order_id,TenantOrder.tenant_id==tenant_id))
        if not order: raise HTTPException(404,"Order not found.")
        if order.payment_status=="COMPLETED" and order.capture_id: return {"status":"COMPLETED","capture_id":order.capture_id,"already_captured":True}
        paypal=provider("POST",_base("sandbox")+f"/v2/checkout/orders/{order.paypal_order_id}/capture",bearer,{},hashlib.sha256(("capture:"+order.paypal_order_id).encode()).hexdigest()[:32])
        captures=[x for pu in paypal.get("purchase_units",[]) for x in (pu.get("payments",{}).get("captures",[]) or [])]
        paid=next((x for x in captures if x.get("status")=="COMPLETED"),None)
        if not paid: return {"status":paypal.get("status","UNKNOWN"),"payment_recorded":False}
        amount=paid.get("amount") or {}
        if amount.get("currency_code")!=order.currency or Decimal(str(amount.get("value","0")))!=Decimal(str(order.amount)).quantize(Decimal("0.01")):
            raise HTTPException(409,"Captured amount differs from the catalog price; refund blocked pending reconciliation.")
        order.capture_id=paid.get("id"); order.payment_status="COMPLETED"
        s.add(TenantAuditEvent(id=str(uuid.uuid4()),tenant_id=tenant_id,actor_user_id=None,event="STOREFRONT_PAYMENT_CAPTURED",entity_type="ORDER",entity_id=order_id,detail={"capture_id":paid.get("id"),"amount":amount,"provider_status":"COMPLETED"}))
        return {"status":"COMPLETED","merchant_order_id":order_id,"capture_id":paid.get("id"),"amount":amount}

@router.get("/api/store/order/{order_id}")
def order_details(order_id:str,access:str):
    tenant_id=grant(order_id,access)
    with tenant_session(tenant_id) as s:
        o=s.scalar(select(TenantOrder).where(TenantOrder.id==order_id,TenantOrder.tenant_id==tenant_id))
        if not o: raise HTTPException(404,"Order not found.")
        rows=s.scalars(select(TenantReview).where(TenantReview.tenant_id==tenant_id,TenantReview.order_id==order_id).order_by(TenantReview.created_at.desc())).all()
        return {"id":o.id,"product":o.product,"amount":str(o.amount),"currency":o.currency,"payment_status":o.payment_status,
            "capture_id":o.capture_id,"complaints":[{"id":r.id,"category":r.category,"text":r.text,"created_at":r.created_at.isoformat()} for r in rows]}

class ComplaintBody(BaseModel):
    category:str=Field(min_length=2,max_length=60)
    message:str=Field(min_length=10,max_length=2000)


@router.post("/api/store/order/{order_id}/complaints/{case_id}/evidence")
async def upload_customer_complaint_evidence(
    order_id: str, case_id: str, access: str,
    evidence_type: str = Form(...), description: str = Form(...),
    file: UploadFile = File(...)
):
    """Customer-token protected evidence upload linked to this exact order and complaint case."""
    tenant_id = grant(order_id, access)
    allowed = {"product_photo", "courier_receipt", "customer_screenshot", "order_document", "other"}
    if evidence_type not in allowed:
        raise HTTPException(400, "Unsupported evidence type.")
    description = description.strip()
    if not 5 <= len(description) <= 1000:
        raise HTTPException(400, "Description must contain 5–1000 characters.")
    mime = (file.content_type or "").lower()
    suffixes = {"image/jpeg": ".jpg", "image/png": ".png", "application/pdf": ".pdf"}
    if mime not in suffixes:
        raise HTTPException(400, "Upload a JPEG, PNG or PDF file.")
    data = await file.read(5 * 1024 * 1024 + 1)
    if not data or len(data) > 5 * 1024 * 1024:
        raise HTTPException(400, "Evidence file must be between 1 byte and 5 MB.")
    valid = ((mime == "image/jpeg" and data.startswith(b"\\xff\\xd8\\xff")) or
             (mime == "image/png" and data.startswith(b"\\x89PNG\\r\\n\\x1a\\n")) or
             (mime == "application/pdf" and data.startswith(b"%PDF-")))
    if not valid:
        raise HTTPException(400, "File signature does not match the selected file type.")
    digest_value = hashlib.sha256(data).hexdigest()
    from pathlib import Path
    from .financial_lifecycle import FinancialEvent
    root = Path(os.getenv("MERCHANTOS_EVIDENCE_DIR", os.getenv("EVIDENCE_UPLOAD_DIR", "/var/data/merchantos-evidence"))).resolve()
    try:
        root.mkdir(parents=True, exist_ok=True)
        os.chmod(root, 0o700)
    except OSError:
        raise HTTPException(503, "Private evidence storage is unavailable; configure the persistent evidence disk.")
    storage_name = uuid.uuid4().hex + suffixes[mime]
    storage_path = root / storage_name
    try:
        storage_path.write_bytes(data)
        os.chmod(storage_path, 0o600)
    except OSError:
        raise HTTPException(503, "Evidence could not be stored securely.")
    try:
        with tenant_session(tenant_id) as session:
            order = session.scalar(select(TenantOrder).where(TenantOrder.id == order_id, TenantOrder.tenant_id == tenant_id))
            case = session.scalar(select(ResolutionCase).where(ResolutionCase.id == case_id, ResolutionCase.tenant_id == tenant_id, ResolutionCase.order_id == order_id))
            if not order or not case:
                raise HTTPException(404, "Complaint or order not found.")
            if order.payment_status != "COMPLETED":
                raise HTTPException(409, "Evidence intake is available after payment capture.")
            duplicate = session.scalar(select(TenantEvidence).where(TenantEvidence.tenant_id == tenant_id, TenantEvidence.sha256 == digest_value))
            if duplicate:
                raise HTTPException(409, "This file is already registered in the merchant evidence vault.")
            evidence_id = "EVD-" + uuid.uuid4().hex[:16].upper()
            session.add(TenantEvidence(id=evidence_id, tenant_id=tenant_id, order_id=order_id,
                evidence_type=evidence_type.upper(), description=description, storage_key=storage_name,
                sha256=digest_value, integrity_status="SHA256_VERIFIED"))
            session.add(FinancialEvent(id=str(uuid.uuid4()), tenant_id=tenant_id, case_id=case_id,
                event_type="EVIDENCE_UPLOADED", actor_id="customer-portal",
                payload={"evidence_id": evidence_id, "evidence_type": evidence_type.upper(), "sha256": digest_value}))
            session.add(TenantAuditEvent(id=str(uuid.uuid4()), tenant_id=tenant_id, actor_user_id=None,
                event="CUSTOMER_COMPLAINT_EVIDENCE_UPLOADED", entity_type="FINANCIAL_CASE", entity_id=case_id,
                detail={"evidence_id": evidence_id, "order_id": order_id, "sha256": digest_value}))
    except Exception:
        try: storage_path.unlink(missing_ok=True)
        except OSError: pass
        raise
    return {"evidence_id": evidence_id, "case_id": case_id, "integrity_status": "SHA256_VERIFIED",
            "message": "Evidence securely registered and linked to this complaint."}

@router.post("/api/store/order/{order_id}/complaints")
def complaint(order_id:str,access:str,body:ComplaintBody):
    tenant_id=grant(order_id,access)
    with tenant_session(tenant_id) as s:
        o=s.scalar(select(TenantOrder).where(TenantOrder.id==order_id,TenantOrder.tenant_id==tenant_id))
        if not o: raise HTTPException(404,"Order not found.")
        if o.payment_status!="COMPLETED": raise HTTPException(409,"Complaint intake opens after payment capture is completed.")
        cid="CMP-"+uuid.uuid4().hex[:12].upper(); case_id=str(uuid.uuid4())
        s.add(TenantReview(id=cid,tenant_id=tenant_id,customer_id=o.customer_id,customer_name=o.customer_name,order_id=o.id,product=o.product,rating=None,text=body.message.strip(),category=body.category.upper(),severity="MEDIUM"))
        s.add(ResolutionCase(id=case_id,tenant_id=tenant_id,order_id=o.id,case_type="REFUND",status="OPEN",reason=body.message.strip(),requested_amount=Decimal(str(o.amount)),estimated_loss=Decimal(str(o.amount)),recoverable_inventory_estimate=Decimal("0"),created_by="customer-portal"))
        s.add(TenantAuditEvent(id=str(uuid.uuid4()),tenant_id=tenant_id,actor_user_id=None,event="CUSTOMER_COMPLAINT_SUBMITTED",entity_type="FINANCIAL_CASE",entity_id=case_id,detail={"complaint_id":cid,"order_id":o.id,"category":body.category.upper()}))
        return {"complaint_id":cid,"case_id":case_id,"status":"OPEN","message":"Complaint received. The merchant can review it in MerchantOS."}
