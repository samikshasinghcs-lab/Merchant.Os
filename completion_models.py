"""Tenant-owned operational security records for MerchantOS v1.3."""
from datetime import datetime, timezone
from sqlalchemy import String, Text, DateTime, ForeignKey, UniqueConstraint, JSON, Boolean, Index, Integer
from sqlalchemy.orm import Mapped, mapped_column
from .orm_base import Base

def utcnow(): return datetime.now(timezone.utc)

class MerchantPayPalCredential(Base):
    __tablename__='merchant_paypal_credentials'
    __table_args__=(UniqueConstraint('tenant_id','environment',name='uq_paypal_credential_tenant_env'),)
    id: Mapped[str]=mapped_column(String(36),primary_key=True)
    tenant_id: Mapped[str]=mapped_column(ForeignKey('tenants.id',ondelete='CASCADE'),nullable=False,index=True)
    environment: Mapped[str]=mapped_column(String(12),nullable=False)
    client_id: Mapped[str]=mapped_column(Text,nullable=False)
    encrypted_client_secret: Mapped[str]=mapped_column(Text,nullable=False)
    webhook_id: Mapped[str]=mapped_column(String(200),nullable=False)
    active: Mapped[bool]=mapped_column(Boolean,default=True,nullable=False)
    updated_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=utcnow,nullable=False)

class PayPalWebhookEvent(Base):
    __tablename__='paypal_webhook_events'
    __table_args__=(UniqueConstraint('tenant_id','event_id',name='uq_paypal_event_tenant_id'),Index('ix_paypal_events_status','tenant_id','status'))
    id: Mapped[str]=mapped_column(String(36),primary_key=True)
    tenant_id: Mapped[str]=mapped_column(ForeignKey('tenants.id',ondelete='CASCADE'),nullable=False,index=True)
    event_id: Mapped[str]=mapped_column(String(200),nullable=False)
    event_type: Mapped[str]=mapped_column(String(200),nullable=False)
    payload: Mapped[dict]=mapped_column(JSON,nullable=False)
    status: Mapped[str]=mapped_column(String(30),default='RECEIVED',nullable=False)
    received_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=utcnow,nullable=False)
    processed_at: Mapped[datetime|None]=mapped_column(DateTime(timezone=True))
    error: Mapped[str|None]=mapped_column(Text)
    attempt_count: Mapped[int]=mapped_column(Integer,default=0,nullable=False)
    next_attempt_at: Mapped[datetime|None]=mapped_column(DateTime(timezone=True))
    locked_until: Mapped[datetime|None]=mapped_column(DateTime(timezone=True))
    workflow_run_id: Mapped[str|None]=mapped_column(String(128))
    work_item: Mapped[dict|None]=mapped_column(JSON)
    dead_lettered_at: Mapped[datetime|None]=mapped_column(DateTime(timezone=True))

class PayPalWebhookRoute(Base):
    """Opaque webhook URL routing registry. Stores only a hash of the random path token."""
    __tablename__='paypal_webhook_routes'
    __table_args__=(UniqueConstraint('token_hash',name='uq_paypal_webhook_route_token_hash'),Index('ix_paypal_webhook_route_tenant','tenant_id','environment'))
    id: Mapped[str]=mapped_column(String(36),primary_key=True)
    tenant_id: Mapped[str]=mapped_column(ForeignKey('tenants.id',ondelete='CASCADE'),nullable=False,index=True)
    environment: Mapped[str]=mapped_column(String(12),nullable=False)
    token_hash: Mapped[str]=mapped_column(String(64),nullable=False)
    active: Mapped[bool]=mapped_column(Boolean,default=True,nullable=False)
    created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=utcnow,nullable=False)

class EventExecutionTrace(Base):
    """Tenant-scoped operational trace. Contains allowlisted metadata, never raw provider payloads."""
    __tablename__='event_execution_traces'
    __table_args__=(Index('ix_event_trace_tenant_event_time','tenant_id','event_id','created_at'),)
    id: Mapped[str]=mapped_column(String(36),primary_key=True)
    tenant_id: Mapped[str]=mapped_column(ForeignKey('tenants.id',ondelete='CASCADE'),nullable=False,index=True)
    event_id: Mapped[str]=mapped_column(String(200),nullable=False,index=True)
    correlation_id: Mapped[str]=mapped_column(String(200),nullable=False)
    phase: Mapped[str]=mapped_column(String(80),nullable=False)
    status: Mapped[str]=mapped_column(String(40),nullable=False)
    detail: Mapped[dict]=mapped_column(JSON,default=dict,nullable=False)
    created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=utcnow,nullable=False)

class PactPartyApproval(Base):
    __tablename__='pact_party_approvals'
    __table_args__=(UniqueConstraint('tenant_id','agreement_id','agreement_version','user_id',name='uq_pact_party_approval'),)
    id: Mapped[str]=mapped_column(String(36),primary_key=True)
    tenant_id: Mapped[str]=mapped_column(ForeignKey('tenants.id',ondelete='CASCADE'),nullable=False,index=True)
    agreement_id: Mapped[str]=mapped_column(String(100),nullable=False,index=True)
    agreement_version: Mapped[int]=mapped_column(nullable=False)
    user_id: Mapped[str]=mapped_column(ForeignKey('users.id',ondelete='CASCADE'),nullable=False)
    decision: Mapped[str]=mapped_column(String(20),nullable=False)
    statement_hash: Mapped[str]=mapped_column(String(64),nullable=False)
    created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=utcnow,nullable=False)

class MerchantInvitation(Base):
    __tablename__='merchant_invitations'
    id: Mapped[str]=mapped_column(String(36),primary_key=True)
    tenant_id: Mapped[str]=mapped_column(ForeignKey('tenants.id',ondelete='CASCADE'),nullable=False,index=True)
    email: Mapped[str]=mapped_column(String(320),nullable=False,index=True)
    role: Mapped[str]=mapped_column(String(20),nullable=False)
    token_hash: Mapped[str]=mapped_column(String(64),nullable=False,unique=True)
    expires_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),nullable=False)
    accepted_at: Mapped[datetime|None]=mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=utcnow,nullable=False)

class FinancialApprovalRequest(Base):
    """Tenant-scoped, immutable-payload approval envelope; no provider write here."""
    __tablename__='financial_approval_requests'
    __table_args__=(UniqueConstraint('tenant_id','request_key',name='uq_fin_approval_tenant_key'),Index('ix_fin_approval_status','tenant_id','status'))
    id: Mapped[str]=mapped_column(String(36),primary_key=True)
    tenant_id: Mapped[str]=mapped_column(ForeignKey('tenants.id',ondelete='CASCADE'),nullable=False,index=True)
    request_key: Mapped[str]=mapped_column(String(128),nullable=False)
    action: Mapped[str]=mapped_column(String(32),nullable=False)
    capture_id: Mapped[str]=mapped_column(String(128),nullable=False)
    amount: Mapped[str]=mapped_column(String(32),nullable=False)
    currency: Mapped[str]=mapped_column(String(3),nullable=False)
    reason: Mapped[str]=mapped_column(Text,nullable=False)
    policy_digest: Mapped[str]=mapped_column(String(64),nullable=False)
    requester_id: Mapped[str]=mapped_column(ForeignKey('users.id'),nullable=False)
    approver_id: Mapped[str|None]=mapped_column(ForeignKey('users.id'))
    status: Mapped[str]=mapped_column(String(32),default='PENDING_RECONCILIATION',nullable=False)
    decision_note: Mapped[str|None]=mapped_column(Text)
    created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=utcnow,nullable=False)
    decided_at: Mapped[datetime|None]=mapped_column(DateTime(timezone=True))

class FinancialExecution(Base):
    """One durable provider execution reservation per approved financial request."""
    __tablename__='financial_executions'
    __table_args__=(UniqueConstraint('tenant_id','approval_id',name='uq_fin_execution_approval'),
                    UniqueConstraint('tenant_id','provider_request_id',name='uq_fin_execution_provider_request'),
                    Index('ix_fin_execution_status','tenant_id','status'))
    id: Mapped[str]=mapped_column(String(36),primary_key=True)
    tenant_id: Mapped[str]=mapped_column(ForeignKey('tenants.id',ondelete='CASCADE'),nullable=False,index=True)
    approval_id: Mapped[str]=mapped_column(ForeignKey('financial_approval_requests.id',ondelete='CASCADE'),nullable=False)
    provider: Mapped[str]=mapped_column(String(20),nullable=False,default='PAYPAL')
    environment: Mapped[str]=mapped_column(String(12),nullable=False)
    provider_request_id: Mapped[str]=mapped_column(String(64),nullable=False)
    status: Mapped[str]=mapped_column(String(24),nullable=False,default='RESERVED')
    provider_refund_id: Mapped[str|None]=mapped_column(String(128))
    provider_status: Mapped[str|None]=mapped_column(String(40))
    error_code: Mapped[str|None]=mapped_column(String(80))
    created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=utcnow,nullable=False)
    completed_at: Mapped[datetime|None]=mapped_column(DateTime(timezone=True))
