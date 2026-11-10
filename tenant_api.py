"""Authenticated tenant-scoped PostgreSQL API. These endpoints never query legacy SQLite."""
import uuid
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from . import auth as identity
from .tenant_db import tenant_session
from .domain_models import TenantOrder, TenantReview, TenantRefund, TenantDispute, TenantEvidence, TenantAuditEvent
from .api_schemas import TenantOrderCreate, TenantReviewCreate

router = APIRouter(prefix='/api/v1/domain', tags=['tenant-domain'])

def principal(p=Depends(identity.current_principal)):
    if not identity.AUTH_AVAILABLE: raise HTTPException(503, 'Identity dependencies unavailable')
    return p

@router.get('/orders')
def orders(p=Depends(principal)):
    with tenant_session(p['tenant_id']) as s:
        return [{'id':x.id,'customer_id':x.customer_id,'customer_name':x.customer_name,'product':x.product,'amount':str(x.amount),'currency':x.currency,'payment_status':x.payment_status,'created_at':x.created_at.isoformat()} for x in s.scalars(select(TenantOrder).where(TenantOrder.tenant_id==p['tenant_id']).order_by(TenantOrder.created_at.desc()).limit(500))]

@router.post('/orders')
def create_order(body: TenantOrderCreate, p=Depends(principal)):
    row=TenantOrder(id=str(uuid.uuid4()),tenant_id=p['tenant_id'],customer_id=body.customer_id,customer_name=body.customer_name,product=body.product,amount=body.amount,currency=body.currency,payment_status='UNPAID')
    with tenant_session(p['tenant_id']) as s: s.add(row)
    return {'id':row.id,'status':'CREATED'}

@router.get('/reviews')
def reviews(p=Depends(principal)):
    with tenant_session(p['tenant_id']) as s:
        return [{'id':x.id,'customer_id':x.customer_id,'order_id':x.order_id,'rating':x.rating,'text':x.text,'category':x.category,'severity':x.severity} for x in s.scalars(select(TenantReview).where(TenantReview.tenant_id==p['tenant_id']).order_by(TenantReview.created_at.desc()).limit(1000))]

@router.post('/reviews')
def create_review(body: TenantReviewCreate, p=Depends(principal)):
    if body.order_id:
        with tenant_session(p['tenant_id']) as s:
            order=s.scalar(select(TenantOrder.id).where(TenantOrder.id==body.order_id, TenantOrder.tenant_id==p['tenant_id']))
        if not order:
            raise HTTPException(404,'Order not found in this merchant workspace')
    row=TenantReview(id=str(uuid.uuid4()),tenant_id=p['tenant_id'],customer_id=body.customer_id,customer_name=body.customer_name,order_id=body.order_id,product=body.product,rating=body.rating,text=body.text,category=None,severity=None)
    with tenant_session(p['tenant_id']) as s: s.add(row)
    return {'id':row.id,'status':'CREATED'}

@router.get('/summary')
def summary(p=Depends(principal)):
    with tenant_session(p['tenant_id']) as s:
        tables=(TenantOrder,TenantReview,TenantRefund,TenantDispute,TenantEvidence,TenantAuditEvent)
        return {t.__tablename__:len(s.scalars(select(t.id).where(t.tenant_id==p['tenant_id'])).all()) for t in tables}
