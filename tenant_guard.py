"""Fail-closed routing guard while legacy business tables remain single-tenant.

The PostgreSQL /api/v1/domain router is tenant-scoped. Legacy SQLite handlers are
not. If operators enable multi-tenant mode before migration is complete, deny
those handlers rather than risk cross-workspace reads or writes.
"""
from __future__ import annotations

TENANT_SCOPED_PREFIXES = (
    "/api/v1/domain/",
)
SAFE_AUTH_PATHS = {
    "/api/auth/login",
    "/api/auth/register",
    "/api/auth/me",
}
# These endpoints validate provider/internal signatures or use tenant-specific
# endpoint tokens and have their own tenant routing. They are not general UI APIs.
SCOPED_EVENT_PREFIXES = (
    "/api/paypal/webhooks/tenant/",
)
SCOPED_EVENT_PATHS = {
    "/api/paypal/webhooks/receive",
    "/api/paypal/webhooks/verify",
    "/api/internal/paypal-events",
    "/api/internal/tenant-paypal-events/process",
}


def legacy_route_blocked(path: str, multi_tenant_enabled: bool) -> bool:
    """Return True when a legacy, unscoped API route must be denied."""
    if not multi_tenant_enabled or not path.startswith("/api/"):
        return False
    if path in SAFE_AUTH_PATHS or path in SCOPED_EVENT_PATHS:
        return False
    if any(path.startswith(prefix) for prefix in TENANT_SCOPED_PREFIXES + SCOPED_EVENT_PREFIXES):
        return False
    return True
