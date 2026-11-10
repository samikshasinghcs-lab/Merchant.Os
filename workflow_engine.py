"""Deterministic event orchestration for MerchantOS.

Webhook events are signals, not proof of current financial state. This module
classifies verified events and creates an auditable reconciliation work item;
it never performs a capture, refund, invoice send, or dispute write.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Optional

@dataclass(frozen=True)
class EventPlan:
    event_type: str
    domain: str
    action: str
    requires_provider_reconciliation: bool = True

_EVENT_ROUTES = {
    "PAYMENT.CAPTURE.COMPLETED": EventPlan("PAYMENT.CAPTURE.COMPLETED", "payment", "reconcile_capture"),
    "PAYMENT.CAPTURE.DENIED": EventPlan("PAYMENT.CAPTURE.DENIED", "payment", "reconcile_capture_failure"),
    "PAYMENT.CAPTURE.REFUNDED": EventPlan("PAYMENT.CAPTURE.REFUNDED", "refund", "reconcile_refund"),
    "PAYMENT.CAPTURE.REVERSED": EventPlan("PAYMENT.CAPTURE.REVERSED", "payment", "reconcile_reversal"),
    "CUSTOMER.DISPUTE.CREATED": EventPlan("CUSTOMER.DISPUTE.CREATED", "dispute", "sync_dispute"),
    "CUSTOMER.DISPUTE.UPDATED": EventPlan("CUSTOMER.DISPUTE.UPDATED", "dispute", "sync_dispute"),
    "CUSTOMER.DISPUTE.RESOLVED": EventPlan("CUSTOMER.DISPUTE.RESOLVED", "dispute", "sync_dispute"),
    "INVOICING.INVOICE.PAID": EventPlan("INVOICING.INVOICE.PAID", "invoice", "reconcile_invoice"),
    "INVOICING.INVOICE.CANCELLED": EventPlan("INVOICING.INVOICE.CANCELLED", "invoice", "reconcile_invoice"),
}

def classify_paypal_event(event_type: str) -> Optional[EventPlan]:
    """Return a deterministic plan for supported events; unknown events are quarantined."""
    return _EVENT_ROUTES.get(str(event_type or "").strip().upper())

def build_reconciliation_work_item(event: dict) -> dict:
    event_id = str(event.get("event_id", "")).strip()
    event_type = str(event.get("event_type", "")).strip().upper()
    if not event_id or not event_type:
        raise ValueError("Event identity is required")
    plan = classify_paypal_event(event_type)
    if plan is None:
        return {"event_id": event_id, "event_type": event_type, "status": "IGNORED_UNSUPPORTED", "domain": "unknown", "action": "none", "requires_provider_reconciliation": False}
    return {"event_id": event_id, "event_type": event_type, "status": "RECONCILIATION_REQUIRED", "domain": plan.domain, "action": plan.action, "requires_provider_reconciliation": plan.requires_provider_reconciliation, "financial_write_authorized": False}
