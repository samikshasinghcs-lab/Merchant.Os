"""Tenant-owned PayPal Sandbox API connections and transaction sync.

Merchants provide their own PayPal REST app credentials. Secrets are Fernet-encrypted
at rest and are never returned by the API. This is credential-based merchant
connection, not PayPal Partner Referrals / third-party delegated OAuth onboarding.
"""
from __future__ import annotations
import os, uuid
from datetime import datetime, timezone, date, timedelta
from decimal import Decimal, InvalidOperation
from typing import Any
import requests
from cryptography.fernet import Fernet, InvalidToken
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import String, DateTime, JSON, Numeric, Integer, ForeignKey, UniqueConstraint, Index, select
from sqlalchemy.orm import Mapped, mapped_column
from .orm_base import Base
from . import auth as identity
from .tenant_db import tenant_session
from .domain_models import TenantAuditEvent

router = APIRouter(prefix="/api/v1/paypal-connection", tags=["tenant-paypal"])

class TenantPayPalConnection(Base):
    __tablename__ = "tenant_paypal_connections"
    __table_args__ = (UniqueConstraint("tenant_id", name="uq_tenant_paypal_connection"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    client_id_enc: Mapped[str] = mapped_column(String(4096), nullable=False)
    client_secret_enc: Mapped[str] = mapped_column(String(4096), nullable=False)
    environment: Mapped[str] = mapped_column(String(16), nullable=False, default="sandbox")
    merchant_account_id: Mapped[str | None] = mapped_column(String(128))
    connected_by: Mapped[str] = mapped_column(String(36), nullable=False)
    connected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    last_sync_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

class TenantPayPalTransaction(Base):
    __tablename__ = "tenant_paypal_transactions"
    __table_args__ = (UniqueConstraint("tenant_id", "paypal_transaction_id", name="uq_tenant_paypal_tx"), Index("ix_tenant_paypal_tx_date", "tenant_id", "transaction_initiation_date"))
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    paypal_transaction_id: Mapped[str] = mapped_column(String(128), nullable=False)
    transaction_status: Mapped[str | None] = mapped_column(String(40))
    transaction_type: Mapped[str | None] = mapped_column(String(80))
    transaction_amount: Mapped[dict] = mapped_column(JSON, nullable=False)
    fee_amount: Mapped[dict | None] = mapped_column(JSON)
    transaction_initiation_date: Mapped[str | None] = mapped_column(String(40))
    transaction_updated_date: Mapped[str | None] = mapped_column(String(40))
    raw_safe: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    synced_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

class ConnectBody(BaseModel):
    client_id: str = Field(min_length=10, max_length=2048)
    client_secret: str = Field(min_length=10, max_length=2048)
    environment: str = "sandbox"

def _principal(p=Depends(identity.current_principal)):
    if not identity.AUTH_AVAILABLE:
        raise HTTPException(503, "Identity service unavailable")
    return p

def _fernet() -> Fernet:
    key = os.getenv("MERCHANTOS_CREDENTIALS_KEY", "")
    try:
        return Fernet(key.encode("ascii"))
    except Exception:
        raise HTTPException(503, "Tenant credential encryption is not configured. Set a valid MERCHANTOS_CREDENTIALS_KEY.")

def _decrypt(value: str) -> str:
    try:
        return _fernet().decrypt(value.encode()).decode()
    except (InvalidToken, ValueError):
        raise HTTPException(503, "Stored PayPal credentials cannot be decrypted. Check the credential encryption key.")

def _base(environment: str) -> str:
    if environment != "sandbox":
        raise HTTPException(400, "Only PayPal Sandbox connections are enabled in this release.")
    return "https://api-m.sandbox.paypal.com"

def _oauth(client_id: str, client_secret: str, environment: str) -> str:
    try:
        response = requests.post(_base(environment) + "/v1/oauth2/token",
            auth=(client_id, client_secret), data={"grant_type": "client_credentials"}, timeout=20)
    except requests.RequestException:
        raise HTTPException(502, "Could not reach PayPal Sandbox OAuth.")
    if not response.ok:
        # Never return provider response bodies: they can contain sensitive diagnostics.
        raise HTTPException(502, "PayPal Sandbox rejected these credentials. Verify the app Client ID and Secret.")
    try:
        return response.json()["access_token"]
    except (ValueError, KeyError, TypeError):
        raise HTTPException(502, "PayPal Sandbox returned an invalid OAuth response.")

def _connection(tenant_id: str):
    with tenant_session(tenant_id) as s:
        row = s.scalar(select(TenantPayPalConnection).where(TenantPayPalConnection.tenant_id == tenant_id))
        if not row:
            raise HTTPException(404, "No PayPal connection exists for this workspace.")
        return {"client_id": _decrypt(row.client_id_enc), "client_secret": _decrypt(row.client_secret_enc),
                "environment": row.environment, "connected_at": row.connected_at.isoformat(),
                "last_sync_at": row.last_sync_at.isoformat() if row.last_sync_at else None}

@router.get("/status")
def status(p=Depends(_principal)):
    with tenant_session(p["tenant_id"]) as s:
        row = s.scalar(select(TenantPayPalConnection).where(TenantPayPalConnection.tenant_id == p["tenant_id"]))
        count = len(s.scalars(select(TenantPayPalTransaction.id).where(TenantPayPalTransaction.tenant_id == p["tenant_id"])).all())
        return {"connected": bool(row), "environment": row.environment if row else None,
                "connected_at": row.connected_at.isoformat() if row else None,
                "last_sync_at": row.last_sync_at.isoformat() if row and row.last_sync_at else None,
                "synced_transaction_count": count, "credentials_exposed": False,
                "connection_type": "merchant_owned_rest_app_credentials"}

@router.post("/connect")
def connect(body: ConnectBody, p=Depends(_principal)):
    if p["role"] not in {"OWNER", "ADMIN"}:
        raise HTTPException(403, "Only workspace owners or admins can connect PayPal.")
    environment = body.environment.strip().lower()
    _base(environment)
    # Validate with PayPal before persisting anything.
    _oauth(body.client_id.strip(), body.client_secret.strip(), environment)
    cipher = _fernet()
    with tenant_session(p["tenant_id"]) as s:
        row = s.scalar(select(TenantPayPalConnection).where(TenantPayPalConnection.tenant_id == p["tenant_id"]))
        if row:
            row.client_id_enc = cipher.encrypt(body.client_id.strip().encode()).decode()
            row.client_secret_enc = cipher.encrypt(body.client_secret.strip().encode()).decode()
            row.environment = environment
            row.connected_by = p["user_id"]
            row.connected_at = datetime.now(timezone.utc)
            row.last_sync_at = None
        else:
            row = TenantPayPalConnection(tenant_id=p["tenant_id"],
                client_id_enc=cipher.encrypt(body.client_id.strip().encode()).decode(),
                client_secret_enc=cipher.encrypt(body.client_secret.strip().encode()).decode(),
                environment=environment, connected_by=p["user_id"])
            s.add(row)
        s.add(TenantAuditEvent(id=str(uuid.uuid4()), tenant_id=p["tenant_id"],
            actor_user_id=p["user_id"], event="PAYPAL_SANDBOX_CONNECTED",
            entity_type="paypal_connection", entity_id=row.id if row.id else "pending",
            detail={"environment": environment, "credential_values_stored": False}))
    return {"connected": True, "environment": environment, "credentials_exposed": False,
            "message": "PayPal Sandbox credentials validated and encrypted for this workspace."}

@router.post("/test")
def test_connection(p=Depends(_principal)):
    c = _connection(p["tenant_id"])
    _oauth(c["client_id"], c["client_secret"], c["environment"])
    return {"ok": True, "provider": "PayPal", "environment": c["environment"], "message": "PayPal Sandbox OAuth succeeded."}

@router.delete("")
def disconnect(p=Depends(_principal)):
    if p["role"] not in {"OWNER", "ADMIN"}:
        raise HTTPException(403, "Only workspace owners or admins can disconnect PayPal.")
    with tenant_session(p["tenant_id"]) as s:
        row = s.scalar(select(TenantPayPalConnection).where(TenantPayPalConnection.tenant_id == p["tenant_id"]))
        if row:
            s.delete(row)
            s.add(TenantAuditEvent(id=str(uuid.uuid4()), tenant_id=p["tenant_id"],
                actor_user_id=p["user_id"], event="PAYPAL_SANDBOX_DISCONNECTED",
                entity_type="paypal_connection", entity_id=row.id, detail={}))
    return {"disconnected": True, "historical_synced_transactions_retained": True}

@router.post("/sync")
def sync_transactions(start_date: str, end_date: str, p=Depends(_principal)):
    try:
        start = date.fromisoformat(start_date)
        end = date.fromisoformat(end_date)
    except ValueError:
        raise HTTPException(400, "Dates must use YYYY-MM-DD.")
    if end < start or (end - start).days > 30 or end > date.today():
        raise HTTPException(400, "Choose a date range of at most 31 days ending today or earlier.")
    c = _connection(p["tenant_id"])
    access_token = _oauth(c["client_id"], c["client_secret"], c["environment"])
    url = _base(c["environment"]) + "/v1/reporting/transactions"
    try:
        response = requests.get(url, headers={"Authorization": "Bearer " + access_token},
            params={"start_date": start.isoformat() + "T00:00:00-0000",
                    "end_date": end.isoformat() + "T23:59:59-0000",
                    "page_size": 100, "page": 1, "fields": "all"}, timeout=30)
    except requests.RequestException:
        raise HTTPException(502, "PayPal transaction reporting request failed.")
    if not response.ok:
        raise HTTPException(502, "PayPal did not return transaction reporting data. Check reporting API access and date range.")
    try:
        items = response.json().get("transaction_details", [])
    except (ValueError, AttributeError):
        raise HTTPException(502, "PayPal returned an invalid transaction report.")
    saved = 0
    with tenant_session(p["tenant_id"]) as s:
        for item in items[:100]:
            info = item.get("transaction_info") or {}
            txid = info.get("transaction_id")
            amount = info.get("transaction_amount") or {}
            if not txid or not isinstance(amount, dict):
                continue
            safe = {"transaction_id": txid, "transaction_status": info.get("transaction_status"),
                "transaction_type": info.get("transaction_event_code"),
                "transaction_amount": amount, "fee_amount": info.get("fee_amount"),
                "transaction_initiation_date": info.get("transaction_initiation_date"),
                "transaction_updated_date": info.get("transaction_updated_date")}
            row = s.scalar(select(TenantPayPalTransaction).where(
                TenantPayPalTransaction.tenant_id == p["tenant_id"],
                TenantPayPalTransaction.paypal_transaction_id == txid))
            if row:
                row.transaction_status = safe["transaction_status"]
                row.transaction_type = safe["transaction_type"]
                row.transaction_amount = amount
                row.fee_amount = safe["fee_amount"]
                row.transaction_initiation_date = safe["transaction_initiation_date"]
                row.transaction_updated_date = safe["transaction_updated_date"]
                row.raw_safe = safe
                row.synced_at = datetime.now(timezone.utc)
            else:
                s.add(TenantPayPalTransaction(tenant_id=p["tenant_id"], paypal_transaction_id=txid,
                    transaction_status=safe["transaction_status"], transaction_type=safe["transaction_type"],
                    transaction_amount=amount, fee_amount=safe["fee_amount"],
                    transaction_initiation_date=safe["transaction_initiation_date"],
                    transaction_updated_date=safe["transaction_updated_date"], raw_safe=safe))
            saved += 1
        connection = s.scalar(select(TenantPayPalConnection).where(TenantPayPalConnection.tenant_id == p["tenant_id"]))
        if connection:
            connection.last_sync_at = datetime.now(timezone.utc)
        s.add(TenantAuditEvent(id=str(uuid.uuid4()), tenant_id=p["tenant_id"],
            actor_user_id=p["user_id"], event="PAYPAL_TRANSACTIONS_SYNCED",
            entity_type="paypal_transaction_report", entity_id=f"{start}:{end}",
            detail={"records_returned": len(items), "records_upserted": saved, "environment": "sandbox"}))
    return {"provider": "PayPal", "environment": "sandbox", "records_returned": len(items),
            "records_upserted": saved, "range": {"start": start.isoformat(), "end": end.isoformat()},
            "source": "PAYPAL_TRANSACTION_REPORTING_API", "next_page_available": len(items) == 100}

@router.get("/transactions")
def transactions(limit: int = 100, p=Depends(_principal)):
    limit = max(1, min(limit, 500))
    with tenant_session(p["tenant_id"]) as s:
        rows = s.scalars(select(TenantPayPalTransaction).where(
            TenantPayPalTransaction.tenant_id == p["tenant_id"]
        ).order_by(TenantPayPalTransaction.transaction_initiation_date.desc()).limit(limit)).all()
        return [{"paypal_transaction_id": x.paypal_transaction_id,
            "status": x.transaction_status, "type": x.transaction_type,
            "amount": x.transaction_amount, "fee": x.fee_amount,
            "initiated_at": x.transaction_initiation_date, "updated_at": x.transaction_updated_date,
            "synced_at": x.synced_at.isoformat(), "source": "PAYPAL_API"} for x in rows]
