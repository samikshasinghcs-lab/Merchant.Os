# MerchantOS v6.4 — Tenant Isolation Containment Guard

## What changed

The identity and PostgreSQL tenant-domain foundation existed, but legacy business endpoints still query shared SQLite tables without tenant ownership. v6.4 adds a fail-closed route guard controlled by `MULTI_TENANT_ENABLED=true`.

When enabled, legacy `/api/*` business routes return HTTP 503 with `LEGACY_ROUTE_NOT_TENANT_SAFE`. The tenant-scoped PostgreSQL `/api/v1/domain/*` router remains reachable, as do authentication endpoints and explicitly scoped/signed provider event routes. When the flag is false or unset, routing behavior is unchanged.

## Why this is a containment control, not completed isolation

This does **not** migrate legacy data, repositories, background jobs, uploads, exports, or all provider workflows to tenant-scoped storage. It prevents the known unscoped legacy HTTP routes from being exposed when an operator enables multi-tenant mode. Keep `MULTI_TENANT_ENABLED=false` for the existing single-workspace demo until the migration is complete; do not enable multi-tenant SaaS onboarding based on this guard alone.

## Verification

- Unit tests cover legacy-route denial, tenant-domain allowlisting, event/auth exceptions, and single-tenant compatibility.
- Python compilation and full test suite results are recorded in the release handoff.
- No live PostgreSQL RLS, PayPal, browser, or deployment test is implied.

## Next required migration work

1. Move every business table and repository to PostgreSQL with `tenant_id` ownership.
2. Bind tenant context to verified principals in every request and background job.
3. Scope uploads, evidence storage, exports, webhook subscriptions, credentials, and audit history.
4. Add composite tenant-aware foreign keys and verify PostgreSQL RLS under the actual application DB role (not table owner/superuser).
5. Add two-tenant integration tests for every read/write/action and run a controlled data backfill.
6. Only then remove the legacy-route block and permit multi-tenant onboarding.
