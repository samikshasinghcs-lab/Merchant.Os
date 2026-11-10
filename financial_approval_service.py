"""Internal transition from canonical provider read to human approval."""
from datetime import datetime, timezone
from decimal import Decimal
from sqlalchemy import select
from .completion_models import FinancialApprovalRequest
from .financial_controls import evaluate_refund
from .tenant_db import tenant_session
from .config import MAX_REFUND, DAILY_CAP


def record_canonical_capture_reconciliation(*, tenant_id: str, approval_id: str,
                                             provider_capture: dict,
                                             already_refunded, daily_total) -> dict:
    """Called only by the trusted PayPal adapter after GET /v2/payments/captures/{id}.

    `provider_capture` must be the parsed response from PayPal, never request data.
    This function performs no financial write to PayPal.
    """
    if already_refunded is None or daily_total is None:
        raise ValueError("Trusted cumulative refunded amount and daily refund total are required")
    if not isinstance(provider_capture, dict) or not isinstance(provider_capture.get("amount"), dict):
        raise ValueError("Canonical PayPal capture response is incomplete")
    # Capture GET does not provide a cumulative refunded amount. Never let a caller
    # promote a partial/refunded capture by supplying a guessed `already_refunded`.
    if str(provider_capture.get("status") or "").upper() != "COMPLETED":
        with tenant_session(tenant_id) as s:
            row=s.scalar(select(FinancialApprovalRequest).where(
                FinancialApprovalRequest.id==approval_id,
                FinancialApprovalRequest.tenant_id==tenant_id))
            if not row: raise LookupError('Approval request not found')
            if row.status!='PENDING_RECONCILIATION':
                raise ValueError('Request is not awaiting reconciliation')
            row.status='BLOCKED'
            row.decision_note='Capture is not in an unreimbursed COMPLETED state; cumulative prior refunds cannot be safely inferred.'
        return {'status':'BLOCKED','reason':'REFUND_HISTORY_NOT_AUTHORITATIVELY_AVAILABLE',
                'provider_status':str(provider_capture.get('status') or 'UNKNOWN').upper()}
    with tenant_session(tenant_id) as s:
        row=s.scalar(select(FinancialApprovalRequest).where(
            FinancialApprovalRequest.id==approval_id,
            FinancialApprovalRequest.tenant_id==tenant_id))
        if not row: raise LookupError('Approval request not found')
        if row.status!='PENDING_RECONCILIATION':
            raise ValueError('Request is not awaiting reconciliation')
        if str(provider_capture.get('id') or '') != row.capture_id:
            row.status='BLOCKED'; row.decision_note='Provider capture ID mismatch'; return {'status':'BLOCKED','reason':'CAPTURE_ID_MISMATCH'}
        amount_data=provider_capture.get('amount') or {}
        decision=evaluate_refund(capture_id=row.capture_id,amount=row.amount,currency=row.currency,
            capture_amount=amount_data.get('value'),capture_currency=amount_data.get('currency_code'),
            already_refunded=already_refunded,daily_total=daily_total,max_refund=MAX_REFUND,
            daily_cap=DAILY_CAP,provider_status=provider_capture.get('status'),reconciliation_verified=True)
        if not decision.allowed:
            row.status='BLOCKED'; row.decision_note=';'.join(decision.reasons)
            return {'status':'BLOCKED','policy':decision.as_dict()}
        row.status='PENDING_APPROVAL'
        row.decision_note='Canonical PayPal capture read reconciled; awaiting independent OWNER/ADMIN approval.'
        return {'status':'PENDING_APPROVAL','policy':decision.as_dict(),'policy_digest':row.policy_digest}


def reconcile_refund_approval(*, tenant_id: str, approval_id: str, adapter=None) -> dict:
    """Fetch canonical PayPal state and advance one refund request safely.

    Only a COMPLETED capture is auto-reconciled. PayPal's capture resource does not
    expose a reliable cumulative refund amount; PARTIALLY_REFUNDED captures therefore
    fail closed instead of guessing the remaining balance. Daily cap accounting uses
    MerchantOS's own durable execution ledger (not refunds made outside MerchantOS).
    """
    from .paypal_tenant_adapter import TenantPayPalAdapter, TenantPayPalError
    from .completion_models import FinancialExecution
    from sqlalchemy import select
    from datetime import datetime, timezone
    from decimal import Decimal

    with tenant_session(tenant_id) as session:
        row = session.scalar(select(FinancialApprovalRequest).where(
            FinancialApprovalRequest.id == approval_id,
            FinancialApprovalRequest.tenant_id == tenant_id))
        if row is None:
            raise LookupError("Approval request not found")
        if row.status != "PENDING_RECONCILIATION":
            raise ValueError("Request is not awaiting reconciliation")
        capture_id = row.capture_id
        currency = row.currency

    client = adapter or TenantPayPalAdapter(tenant_id, "sandbox")
    provider_capture = client.get_capture(capture_id)
    if not isinstance(provider_capture, dict) or str(provider_capture.get("id") or "") != capture_id:
        return record_canonical_capture_reconciliation(tenant_id=tenant_id, approval_id=approval_id,
            provider_capture=provider_capture if isinstance(provider_capture, dict) else {},
            already_refunded="0.00", daily_total="0.00")

    # A completed capture is the only status for which zero prior refunds can be
    # asserted from the canonical capture status. A partial/full refund needs a
    # separate authoritative refund ledger, so do not infer an amount.
    status = str(provider_capture.get("status") or "").upper()
    if status != "COMPLETED":
        with tenant_session(tenant_id) as session:
            row = session.scalar(select(FinancialApprovalRequest).where(
                FinancialApprovalRequest.id == approval_id,
                FinancialApprovalRequest.tenant_id == tenant_id))
            if row is None:
                raise LookupError("Approval request not found")
            if row.status != "PENDING_RECONCILIATION":
                raise ValueError("Request is not awaiting reconciliation")
            row.status = "BLOCKED"
            row.decision_note = "Capture is not in an unreimbursed COMPLETED state; cumulative prior refunds cannot be safely inferred."
        return {"status": "BLOCKED", "reason": "REFUND_HISTORY_NOT_AUTHORITATIVELY_AVAILABLE",
                "provider_status": status or "UNKNOWN"}

    # Count all MerchantOS refund executions created since UTC midnight, including
    # reserved/unknown outcomes so ambiguous writes consume capacity conservatively.
    now = datetime.now(timezone.utc)
    day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    with tenant_session(tenant_id) as session:
        rows = session.scalars(select(FinancialApprovalRequest.amount).join(
            FinancialExecution, FinancialExecution.approval_id == FinancialApprovalRequest.id
        ).where(
            FinancialExecution.tenant_id == tenant_id,
            FinancialApprovalRequest.tenant_id == tenant_id,
            FinancialExecution.created_at >= day_start,
            FinancialExecution.status.in_(["RESERVED", "SUCCEEDED", "UNKNOWN"]),
            FinancialApprovalRequest.currency == currency,
        )).all()
    daily_total = sum((Decimal(str(value)) for value in rows), Decimal("0.00"))
    return record_canonical_capture_reconciliation(tenant_id=tenant_id, approval_id=approval_id,
        provider_capture=provider_capture, already_refunded="0.00", daily_total=f"{daily_total:.2f}")
