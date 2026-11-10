"""Render Workflows entry points for verified PayPal event processing.

All tasks operate on a durable, tenant-scoped inbox record. They classify a sanitized
event and emit an auditable reconciliation work item; they never execute financial writes.
Run locally with: render workflows dev -- python -m app.render_workflows
"""
from __future__ import annotations

import os
import requests
from render import Retry, TaskContext, Workflows

_RETRY = Retry(max_retries=5, wait_duration_ms=5000, backoff_scaling=2)
app = Workflows(default_retry=_RETRY, default_timeout=90)


def _callback(path: str, body: dict) -> dict:
    base_url = os.getenv("PUBLIC_APP_URL", "").rstrip("/")
    shared_secret = os.getenv("MERCHANTOS_WORKFLOW_SHARED_SECRET", "")
    if not base_url.startswith("https://") or len(shared_secret) < 32:
        raise RuntimeError("Workflow callback URL or shared secret is not configured")
    response = requests.post(
        f"{base_url}{path}", json=body,
        headers={"X-MerchantOS-Workflow-Secret": shared_secret}, timeout=(5, 20),
    )
    response.raise_for_status()
    return response.json()


@app.task(name="process_paypal_event", retry=_RETRY, timeout_seconds=90)
def process_paypal_event(ctx: TaskContext, event: dict) -> dict:
    """Legacy single-workspace event callback. Input must already be sanitized/verified."""
    event_id = str(event.get("event_id", "")).strip()
    event_type = str(event.get("event_type", "")).strip()
    if not event_id or len(event_id) > 128 or not event_type or len(event_type) > 160:
        raise ValueError("Invalid sanitized PayPal event envelope")
    result = _callback("/api/internal/paypal-events", {
        "event": event,
        "work_item": _build_work_item(event),
        "workflow_run_id": getattr(getattr(ctx, "metadata", None), "task_run_id", None),
    })
    return {"event_id": event_id, "event_type": event_type, "result": result}


@app.task(name="process_tenant_paypal_event", retry=_RETRY, timeout_seconds=90)
def process_tenant_paypal_event(ctx: TaskContext, tenant_id: str, event_id: str) -> dict:
    """Process an already-verified event by tenant-scoped inbox identity only."""
    if not tenant_id or len(tenant_id) > 36 or not event_id or len(event_id) > 200:
        raise ValueError("Invalid tenant/event identity")
    result = _callback("/api/internal/tenant-paypal-events/process", {
        "tenant_id": tenant_id, "event_id": event_id,
    })
    return {"tenant_id": tenant_id, "event_id": event_id, "result": result}


def _build_work_item(event: dict) -> dict:
    from .workflow_engine import build_reconciliation_work_item
    return build_reconciliation_work_item(event)


if __name__ == "__main__":
    app.start()
