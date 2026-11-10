"""Durable tenant-scoped PayPal webhook inbox processor.

The processor classifies verified, sanitized webhook envelopes into reconciliation
work items. Webhooks are never treated as canonical payment truth and never authorize
financial writes. Provider reads/reconciliation are separate tasks and human actions
remain behind the existing approval/execution controls.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select

from .completion_models import EventExecutionTrace, PayPalWebhookEvent
from .tenant_db import tenant_session
from .workflow_engine import build_reconciliation_work_item

TERMINAL_STATUSES = {"RECONCILIATION_REQUIRED", "IGNORED_UNSUPPORTED", "DEAD_LETTER"}
MAX_ATTEMPTS = 5
BASE_RETRY_SECONDS = 30
MAX_RETRY_SECONDS = 3600
LEASE_SECONDS = 120


def _utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _trace(session, tenant_id: str, event_id: str, phase: str, status: str, detail: dict[str, Any] | None = None):
    # Only known operational metadata is permitted in traces. Never pass raw PayPal
    # payloads, payer data, credentials, tokens, evidence bytes or model reasoning.
    allowed = {"event_type", "domain", "action", "attempt", "retry_in_seconds", "error_class", "workflow_run_id"}
    safe_detail = {str(k): v for k, v in (detail or {}).items() if k in allowed}
    session.add(EventExecutionTrace(
        id=str(uuid.uuid4()), tenant_id=tenant_id, event_id=event_id,
        correlation_id=f"paypal-event:{tenant_id}:{event_id}", phase=phase[:80],
        status=status[:40], detail=safe_detail,
    ))


def process_event_once(
    tenant_id: str,
    event_id: str,
    *,
    now: datetime | None = None,
    max_attempts: int = MAX_ATTEMPTS,
    base_retry_seconds: int = BASE_RETRY_SECONDS,
    force_due: bool = False,
) -> dict:
    """Claim and process one inbox event once.

    `force_due` is reserved for an authenticated workflow retry callback. It bypasses
    the local retry timestamp, not an active processing lease or terminal state.
    """
    if not tenant_id or not event_id:
        raise ValueError("tenant_id and event_id are required")
    now = _utc(now or datetime.now(timezone.utc))
    payload: dict | None = None
    attempt = 0

    with tenant_session(tenant_id) as session:
        row = session.scalar(
            select(PayPalWebhookEvent)
            .where(PayPalWebhookEvent.tenant_id == tenant_id, PayPalWebhookEvent.event_id == event_id)
            .with_for_update(skip_locked=True)
        )
        if row is None:
            raise LookupError("Webhook event not found")
        if row.status in TERMINAL_STATUSES:
            return {"event_id": event_id, "status": row.status, "attempt_count": row.attempt_count, "duplicate": True}
        locked_until = _utc(row.locked_until)
        if row.status == "PROCESSING" and locked_until and locked_until > now:
            return {"event_id": event_id, "status": "BUSY", "attempt_count": row.attempt_count, "retryable": True}
        next_attempt = _utc(row.next_attempt_at)
        if row.status == "RETRY_WAIT" and next_attempt and next_attempt > now and not force_due:
            return {"event_id": event_id, "status": "NOT_DUE", "attempt_count": row.attempt_count,
                    "next_attempt_at": next_attempt.isoformat()}
        if row.status not in {"RECEIVED", "RETRY_WAIT", "PROCESSING"}:
            return {"event_id": event_id, "status": row.status, "attempt_count": row.attempt_count}
        row.status = "PROCESSING"
        row.attempt_count = int(row.attempt_count or 0) + 1
        attempt = row.attempt_count
        row.locked_until = now + timedelta(seconds=LEASE_SECONDS)
        row.next_attempt_at = None
        payload = dict(row.payload or {})
        _trace(session, tenant_id, event_id, "EVENT_PROCESSING_STARTED", "PROCESSING",
               {"event_type": row.event_type, "attempt": attempt, "workflow_run_id": row.workflow_run_id})

    try:
        if not payload:
            raise ValueError("Sanitized webhook envelope is empty")
        work_item = build_reconciliation_work_item(payload)
    except Exception as exc:
        permanent = isinstance(exc, (ValueError, TypeError, KeyError))
        exhausted = attempt >= max_attempts
        dead = permanent or exhausted
        retry_seconds = min(max_retry_seconds(base_retry_seconds, attempt), MAX_RETRY_SECONDS)
        with tenant_session(tenant_id) as session:
            row = session.scalar(select(PayPalWebhookEvent).where(
                PayPalWebhookEvent.tenant_id == tenant_id, PayPalWebhookEvent.event_id == event_id
            ).with_for_update())
            if row and row.status == "PROCESSING":
                row.status = "DEAD_LETTER" if dead else "RETRY_WAIT"
                row.error = f"{type(exc).__name__}: webhook processing failed"[:500]
                row.locked_until = None
                row.processed_at = now if dead else None
                row.next_attempt_at = None if dead else now + timedelta(seconds=retry_seconds)
                row.dead_lettered_at = now if dead else None
                _trace(session, tenant_id, event_id,
                       "EVENT_DEAD_LETTERED" if dead else "EVENT_RETRY_SCHEDULED", row.status,
                       {"event_type": row.event_type, "attempt": attempt,
                        "retry_in_seconds": None if dead else retry_seconds,
                        "error_class": type(exc).__name__})
        return {"event_id": event_id, "status": "DEAD_LETTER" if dead else "RETRY_WAIT",
                "attempt_count": attempt, "automatic_financial_action": False,
                "retry_in_seconds": None if dead else retry_seconds,
                "error_class": type(exc).__name__}

    with tenant_session(tenant_id) as session:
        row = session.scalar(select(PayPalWebhookEvent).where(
            PayPalWebhookEvent.tenant_id == tenant_id, PayPalWebhookEvent.event_id == event_id
        ).with_for_update())
        if row is None:
            raise LookupError("Webhook event disappeared during processing")
        if row.status != "PROCESSING":
            return {"event_id": event_id, "status": row.status, "attempt_count": row.attempt_count, "stale_worker": True}
        row.work_item = work_item
        row.status = work_item["status"]
        row.processed_at = now
        row.locked_until = None
        row.next_attempt_at = None
        row.error = None
        _trace(session, tenant_id, event_id, "EVENT_CLASSIFIED", row.status,
               {"event_type": row.event_type, "domain": work_item.get("domain"), "action": work_item.get("action")})
        return {"event_id": event_id, "status": row.status, "attempt_count": row.attempt_count,
                "work_item": work_item, "financial_write_authorized": False}


def max_retry_seconds(base: int, attempt: int) -> int:
    return max(1, base) * (2 ** max(0, attempt - 1))


def process_pending_events(tenant_id: str, *, limit: int = 10, now: datetime | None = None) -> dict:
    if not 1 <= int(limit) <= 25:
        raise ValueError("limit must be between 1 and 25")
    now = _utc(now or datetime.now(timezone.utc))
    with tenant_session(tenant_id) as session:
        rows = session.scalars(select(PayPalWebhookEvent).where(
            PayPalWebhookEvent.tenant_id == tenant_id,
            PayPalWebhookEvent.status.in_(["RECEIVED", "RETRY_WAIT", "PROCESSING"]),
        ).order_by(PayPalWebhookEvent.received_at.asc()).limit(200)).all()
        candidates = []
        for row in rows:
            if row.status == "RECEIVED":
                candidates.append(row.event_id)
            elif row.status == "RETRY_WAIT":
                due = _utc(row.next_attempt_at)
                if due is None or due <= now:
                    candidates.append(row.event_id)
            elif row.status == "PROCESSING":
                lease = _utc(row.locked_until)
                if lease is None or lease <= now:
                    candidates.append(row.event_id)
            if len(candidates) >= limit:
                break
    results = [process_event_once(tenant_id, item, now=now) for item in candidates]
    return {"processed": sum(1 for item in results if item.get("status") in TERMINAL_STATUSES - {"DEAD_LETTER"}),
            "retry_wait": sum(1 for item in results if item.get("status") == "RETRY_WAIT"),
            "dead_lettered": sum(1 for item in results if item.get("status") == "DEAD_LETTER"),
            "busy": sum(1 for item in results if item.get("status") in {"BUSY", "NOT_DUE"}),
            "items": results, "financial_writes_performed": 0}


def replay_dead_letter(tenant_id: str, event_id: str, *, actor_id: str):
    if not actor_id:
        raise PermissionError("Authenticated operator identity is required")
    with tenant_session(tenant_id) as session:
        row = session.scalar(select(PayPalWebhookEvent).where(
            PayPalWebhookEvent.tenant_id == tenant_id, PayPalWebhookEvent.event_id == event_id
        ).with_for_update())
        if row is None:
            raise LookupError("Webhook event not found")
        if row.status != "DEAD_LETTER":
            raise ValueError("Only DEAD_LETTER events can be replayed")
        row.status = "RECEIVED"
        row.attempt_count = 0
        row.next_attempt_at = None
        row.locked_until = None
        row.error = None
        row.processed_at = None
        row.dead_lettered_at = None
        _trace(session, tenant_id, event_id, "EVENT_REPLAY_REQUESTED", "RECEIVED", {"attempt": 0})
        return {"event_id": event_id, "status": "RECEIVED", "replayed_by": actor_id,
                "note": "Event will be reclassified only; provider reconciliation and all financial actions remain separate."}


def list_event_trace(tenant_id: str, event_id: str, *, limit: int = 100) -> list[dict]:
    if not 1 <= int(limit) <= 200:
        raise ValueError("limit must be between 1 and 200")
    with tenant_session(tenant_id) as session:
        rows = session.scalars(select(EventExecutionTrace).where(
            EventExecutionTrace.tenant_id == tenant_id,
            EventExecutionTrace.event_id == event_id,
        ).order_by(EventExecutionTrace.created_at.asc()).limit(limit)).all()
        return [{"id": row.id, "event_id": row.event_id, "correlation_id": row.correlation_id,
                 "phase": row.phase, "status": row.status, "detail": row.detail,
                 "created_at": _utc(row.created_at).isoformat()} for row in rows]


def list_webhook_events(tenant_id: str, *, limit: int = 100) -> list[dict]:
    if not 1 <= int(limit) <= 200:
        raise ValueError("limit must be between 1 and 200")
    with tenant_session(tenant_id) as session:
        rows = session.scalars(select(PayPalWebhookEvent).where(
            PayPalWebhookEvent.tenant_id == tenant_id
        ).order_by(PayPalWebhookEvent.received_at.desc()).limit(limit)).all()
        return [{"event_id": row.event_id, "event_type": row.event_type, "status": row.status,
                 "attempt_count": row.attempt_count, "workflow_run_id": row.workflow_run_id,
                 "next_attempt_at": _utc(row.next_attempt_at).isoformat() if row.next_attempt_at else None,
                 "received_at": _utc(row.received_at).isoformat(),
                 "processed_at": _utc(row.processed_at).isoformat() if row.processed_at else None,
                 "error": row.error} for row in rows]
