"""Data-minimizing PayPal webhook envelope helpers for workflow dispatch."""
from __future__ import annotations


def sanitize_paypal_event(event: dict) -> dict:
    if not isinstance(event, dict):
        raise ValueError("PayPal webhook event must be an object")
    event_id = str(event.get("id") or "").strip()
    event_type = str(event.get("event_type") or "").strip()
    if not event_id or len(event_id) > 128 or not event_type or len(event_type) > 160:
        raise ValueError("Webhook event ID or type is invalid")
    resource = event.get("resource") if isinstance(event.get("resource"), dict) else {}
    amount = resource.get("amount") if isinstance(resource.get("amount"), dict) else {}
    return {
        "event_id": event_id,
        "event_type": event_type,
        "create_time": str(event.get("create_time") or "")[:40],
        "resource_type": str(resource.get("object_type") or resource.get("resource_type") or "")[:80],
        "resource_id": str(resource.get("id") or "")[:128],
        "resource_status": str(resource.get("status") or "")[:80],
        "amount_value": str(amount.get("value") or "")[:32],
        "amount_currency": str(amount.get("currency_code") or "")[:8],
    }
