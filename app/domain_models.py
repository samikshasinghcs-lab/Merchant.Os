"""Tenant-scoped PostgreSQL domain schema for MerchantOS v1.1.

These models are the target persistence layer. Legacy SQLite route handlers are
intentionally not switched over until their repository calls are tenant-scoped.
"""
from datetime import datetime, timezone
from sqlalchemy import String, Text, DateTime, Numeric, Integer, ForeignKey, UniqueConstraint, Index, JSON, Boolean
from sqlalchemy.orm import Mapped, mapped_column
from .orm_base import Base


def now_utc(): return datetime.now(timezone.utc)

class TenantOrder(Base):
    __tablename__ = 'merchant_orders'
    __table_args__ = (UniqueConstraint('tenant_id','id',name='uq_order_tenant_id'), Index('ix_orders_tenant_created','tenant_id','created_at'))
    id: Mapped[str] = mapped_column(String(100), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False, index=True)
    customer_id: Mapped[str|None] = mapped_column(String(100))
    customer_name: Mapped[str|None] = mapped_column(String(200))
    product: Mapped[str|None] = mapped_column(String(300))
    batch: Mapped[str|None] = mapped_column(String(100))
    amount: Mapped[float] = mapped_column(Numeric(14,2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    paypal_order_id: Mapped[str|None] = mapped_column(String(100))
    capture_id: Mapped[str|None] = mapped_column(String(100))
    payment_status: Mapped[str] = mapped_column(String(30), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, nullable=False)
    delivered_at: Mapped[datetime|None] = mapped_column(DateTime(timezone=True), nullable=True)
    shipped_at: Mapped[datetime|None] = mapped_column(DateTime(timezone=True), nullable=True)
    hygiene_item: Mapped[bool|None] = mapped_column(Boolean, nullable=True)

class TenantReview(Base):
    __tablename__='merchant_reviews'
    __table_args__=(UniqueConstraint('tenant_id','id',name='uq_review_tenant_id'),Index('ix_reviews_tenant_order','tenant_id','order_id'))
    id: Mapped[str]=mapped_column(String(100),primary_key=True)
    tenant_id: Mapped[str]=mapped_column(ForeignKey('tenants.id',ondelete='CASCADE'),nullable=False,index=True)
    customer_id: Mapped[str|None]=mapped_column(String(100)); customer_name: Mapped[str|None]=mapped_column(String(200))
    order_id: Mapped[str|None]=mapped_column(String(100)); product: Mapped[str|None]=mapped_column(String(300))
    rating: Mapped[int|None]=mapped_column(Integer); text: Mapped[str]=mapped_column(Text,nullable=False)
    category: Mapped[str|None]=mapped_column(String(100)); severity: Mapped[str|None]=mapped_column(String(30))
    complaint_cluster_id: Mapped[str|None]=mapped_column(String(100),nullable=True)
    created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now_utc,nullable=False)

class TenantRefund(Base):
    __tablename__='merchant_refunds'
    __table_args__=(UniqueConstraint('tenant_id','id',name='uq_refund_tenant_id'),UniqueConstraint('tenant_id','idempotency_key',name='uq_refund_tenant_idem'),Index('ix_refunds_tenant_status','tenant_id','status'))
    id: Mapped[str]=mapped_column(String(100),primary_key=True)
    tenant_id: Mapped[str]=mapped_column(ForeignKey('tenants.id',ondelete='CASCADE'),nullable=False,index=True)
    order_id: Mapped[str]=mapped_column(String(100),nullable=False)
    capture_id: Mapped[str|None]=mapped_column(String(100)); amount: Mapped[float]=mapped_column(Numeric(14,2),nullable=False)
    currency: Mapped[str]=mapped_column(String(3),nullable=False); reason: Mapped[str]=mapped_column(Text,nullable=False)
    status: Mapped[str]=mapped_column(String(30),nullable=False); idempotency_key: Mapped[str]=mapped_column(String(200),nullable=False)
    paypal_refund_id: Mapped[str|None]=mapped_column(String(100)); paypal_status: Mapped[str|None]=mapped_column(String(30))
    created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now_utc,nullable=False)

class TenantDispute(Base):
    __tablename__='merchant_disputes'
    __table_args__=(UniqueConstraint('tenant_id','id',name='uq_dispute_tenant_id'),Index('ix_disputes_tenant_status','tenant_id','status'))
    id: Mapped[str]=mapped_column(String(100),primary_key=True)
    tenant_id: Mapped[str]=mapped_column(ForeignKey('tenants.id',ondelete='CASCADE'),nullable=False,index=True)
    order_id: Mapped[str|None]=mapped_column(String(100)); reason: Mapped[str]=mapped_column(Text,nullable=False)
    status: Mapped[str]=mapped_column(String(40),nullable=False); customer_message: Mapped[str|None]=mapped_column(Text)
    evidence: Mapped[dict]=mapped_column(JSON,default=dict,nullable=False)
    created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now_utc,nullable=False)

class TenantEvidence(Base):
    __tablename__='merchant_evidence'
    __table_args__=(UniqueConstraint('tenant_id','id',name='uq_evidence_tenant_id'),Index('ix_evidence_tenant_order','tenant_id','order_id'))
    id: Mapped[str]=mapped_column(String(100),primary_key=True)
    tenant_id: Mapped[str]=mapped_column(ForeignKey('tenants.id',ondelete='CASCADE'),nullable=False,index=True)
    order_id: Mapped[str]=mapped_column(String(100),nullable=False); evidence_type: Mapped[str]=mapped_column(String(80),nullable=False)
    description: Mapped[str]=mapped_column(Text,nullable=False); storage_key: Mapped[str|None]=mapped_column(String(500))
    sha256: Mapped[str|None]=mapped_column(String(64)); integrity_status: Mapped[str]=mapped_column(String(30),default='UNVERIFIED',nullable=False)
    created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now_utc,nullable=False)

class TenantAuditEvent(Base):
    __tablename__='merchant_audit_events'
    __table_args__=(Index('ix_audit_tenant_created','tenant_id','created_at'),)
    id: Mapped[str]=mapped_column(String(100),primary_key=True)
    tenant_id: Mapped[str]=mapped_column(ForeignKey('tenants.id',ondelete='CASCADE'),nullable=False,index=True)
    actor_user_id: Mapped[str|None]=mapped_column(ForeignKey('users.id',ondelete='SET NULL'))
    event: Mapped[str]=mapped_column(String(100),nullable=False); entity_type: Mapped[str]=mapped_column(String(80),nullable=False)
    entity_id: Mapped[str]=mapped_column(String(100),nullable=False); detail: Mapped[dict]=mapped_column(JSON,default=dict,nullable=False)
    created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now_utc,nullable=False)
