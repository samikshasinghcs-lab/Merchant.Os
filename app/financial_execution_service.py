"""Approval-gated, idempotent PayPal refund execution with ambiguity-safe state handling."""
from datetime import datetime, timezone
import hashlib, uuid
from decimal import Decimal, InvalidOperation
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from .tenant_db import tenant_session
from .completion_models import FinancialApprovalRequest, FinancialExecution
from .financial_controls import approval_digest
from .paypal_tenant_adapter import TenantPayPalAdapter, TenantPayPalError
from .execution_state_machine import transition_execution

class ExecutionError(RuntimeError):
    pass

def execute_approved_refund(*, tenant_id: str, approval_id: str, actor_id: str,
                            environment: str = "sandbox", execution_enabled: bool = False) -> dict:
    if not execution_enabled:
        raise PermissionError("PayPal execution is disabled; set PAYPAL_EXECUTION_ENABLED=true after sandbox validation")
    if environment != "sandbox":
        raise PermissionError("Phase 4 only permits sandbox execution; live-money execution is deliberately disabled")
    # Validate tenant credentials before reserving an execution slot.
    adapter=TenantPayPalAdapter(tenant_id, environment)
    # Load and validate tenant-scoped approved intent before reserving a provider request ID.
    with tenant_session(tenant_id) as s:
        row=s.scalar(select(FinancialApprovalRequest).where(
            FinancialApprovalRequest.id==approval_id, FinancialApprovalRequest.tenant_id==tenant_id))
        if not row:
            raise LookupError("Approval request not found")
        if row.status != "APPROVED" or not row.approver_id or row.approver_id == row.requester_id:
            raise PermissionError("A valid independent human approval is required")
        expected=approval_digest(tenant_id=row.tenant_id,capture_id=row.capture_id,amount=row.amount,
                                 currency=row.currency,reason=row.reason)
        if expected != row.policy_digest:
            raise PermissionError("Approved financial payload digest no longer matches")
        if actor_id not in {row.approver_id}:
            raise PermissionError("Only the recorded approver may initiate this execution")
        existing=s.scalar(select(FinancialExecution).where(
            FinancialExecution.tenant_id==tenant_id, FinancialExecution.approval_id==approval_id))
        if existing:
            return _execution_result(existing, replay=True)
        request_id=hashlib.sha256(f"merchantos:{tenant_id}:{approval_id}".encode()).hexdigest()[:32]
        execution=FinancialExecution(id=str(uuid.uuid4()),tenant_id=tenant_id,approval_id=approval_id,
            environment=environment,provider_request_id=request_id,status="RESERVED")
        s.add(execution)
        try:
            s.flush()
        except IntegrityError:
            s.rollback()
            with tenant_session(tenant_id) as retry:
                existing=retry.scalar(select(FinancialExecution).where(
                    FinancialExecution.tenant_id==tenant_id,FinancialExecution.approval_id==approval_id))
                if existing: return _execution_result(existing,replay=True)
            raise ExecutionError("Execution reservation conflict; inspect ledger before retrying")
        # Persist reservation before network I/O. A crash after this point is not blindly retried.
        execution_id=execution.id

    try:
        capture=adapter.get_capture(row.capture_id)
        if str(capture.get("id") or "") != row.capture_id:
            raise TenantPayPalError("Canonical capture ID mismatch", status_code=409)
        amount=capture.get("amount") or {}
        if str(amount.get("currency_code") or "").upper() != row.currency:
            raise TenantPayPalError("Canonical capture currency mismatch", status_code=409)
        try:
            if Decimal(str(amount.get("value") or "0")) < Decimal(row.amount):
                raise TenantPayPalError("Requested refund exceeds canonical capture amount", status_code=409)
        except (InvalidOperation, ValueError):
            raise TenantPayPalError("Canonical capture amount is malformed", status_code=409)
        if str(capture.get("status") or "").upper() not in {"COMPLETED", "PARTIALLY_REFUNDED"}:
            raise TenantPayPalError("Canonical capture is not refundable", status_code=409)
        # PayPal enforces the actual remaining refundable balance; the API request is
        # idempotent. We never infer prior refund totals from an incomplete capture object.
        result=adapter.refund_capture(row.capture_id,row.amount,row.currency,request_id)
        refund_id=str(result.get("id") or "").strip()
        provider_status=str(result.get("status") or "").upper().strip()
        if not refund_id or provider_status not in {"COMPLETED", "PENDING"}:
            # A 2xx without a stable provider refund ID/status cannot be represented as
            # success. The provider may nevertheless have accepted the write.
            with tenant_session(tenant_id) as s:
                item=s.get(FinancialExecution,execution_id)
                transition_execution(item, "UNKNOWN"); item.error_code="MALFORMED_PROVIDER_RESPONSE"
                item.provider_refund_id=refund_id or None; item.provider_status=provider_status[:40] or "UNKNOWN"
                item.completed_at=datetime.now(timezone.utc)
            return {"execution_id":execution_id,"status":"UNKNOWN","provider":"PAYPAL",
                    "environment":environment,"error":"PayPal response did not contain a verifiable refund identifier and accepted status.",
                    "automatic_retry":False,"replay":False}
        with tenant_session(tenant_id) as s:
            item=s.get(FinancialExecution,execution_id)
            transition_execution(item, "SUCCEEDED" if provider_status == "COMPLETED" else "SUBMITTED")
            item.provider_refund_id=refund_id
            item.provider_status=provider_status[:40]
            item.completed_at=datetime.now(timezone.utc)
            # PayPal accepted the refund operation. Settlement/final status must still
            # be read from PayPal; PENDING is not reported as a completed refund.
            approved=s.scalar(select(FinancialApprovalRequest).where(
                FinancialApprovalRequest.id==approval_id,FinancialApprovalRequest.tenant_id==tenant_id))
            approved.status="EXECUTED" if provider_status == "COMPLETED" else "SUBMITTED"
        return {"execution_id":execution_id,"status":"SUCCEEDED" if provider_status=="COMPLETED" else "SUBMITTED",
                "provider":"PAYPAL","environment":environment,"provider_refund_id":refund_id,
                "provider_status":provider_status,"replay":False,
                "settlement_confirmed":provider_status=="COMPLETED"}
    except TenantPayPalError as exc:
        with tenant_session(tenant_id) as s:
            item=s.get(FinancialExecution,execution_id)
            transition_execution(item, "UNKNOWN" if exc.ambiguous else "FAILED")
            item.error_code="PROVIDER_OUTCOME_UNKNOWN" if exc.ambiguous else f"PAYPAL_HTTP_{exc.status_code or 'ERROR'}"
            item.completed_at=datetime.now(timezone.utc)
        return {"execution_id":execution_id,"status":"UNKNOWN" if exc.ambiguous else "FAILED",
                "error":"Provider outcome must be inspected; do not create a new refund request." if exc.ambiguous else str(exc),
                "automatic_retry":False}

def _execution_result(item, replay=False):
    return {"execution_id":item.id,"status":item.status,"provider":item.provider,
            "environment":item.environment,"provider_refund_id":item.provider_refund_id,
            "provider_status":item.provider_status,"replay":replay,
            "automatic_retry":False if item.status in {"RESERVED","SUBMITTED","RECONCILING","UNKNOWN","SUCCEEDED"} else None}
