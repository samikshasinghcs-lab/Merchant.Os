# MerchantOS v1.1 — Tenant Data Foundation

## Delivered in this checkpoint

- Added SQLAlchemy domain models for orders, reviews, refunds, disputes, evidence, and audit events. Every domain row has a non-null `tenant_id` foreign key to `tenants`.
- Added Alembic revision `0002_tenant_domain` after the existing identity migration.
- PostgreSQL migration enables and forces row-level security on all six new domain tables. Policies require `app.tenant_id` to be set for each transaction; missing context returns no rows and rejects writes.
- Added `tenant_session()` which accepts a verified tenant ID, sets transaction-local PostgreSQL context, and commits/rolls back safely.
- Added `require_tenant()` fail-closed guard and tests for tenant columns, unscoped access rejection, and tenant-scoped refund idempotency uniqueness.

## Important boundary — not yet multi-tenant production

This is the tenant-aware PostgreSQL schema foundation, **not the completed migration of the running application**. Existing business routes and intelligence modules still use the legacy SQLite database and are not yet switched to these ORM tables. Existing demo records have not been backfilled. The login token's tenant claim is not yet wired into every business repository. Consequently:

- Do not enable multiple merchant workspaces in production.
- Keep the v1.0 single-workspace registration restriction.
- Do not claim end-to-end tenant isolation yet.
- Do not expose the service publicly with real merchant data until all routes use tenant-scoped repositories and cross-tenant integration tests pass.

## Next required work

1. Build a controlled, idempotent SQLite-to-PostgreSQL backfill with explicit tenant ownership mapping and reconciliation counts.
2. Replace every SQLite business query with tenant-scoped SQLAlchemy repositories.
3. Apply tenant context from the verified JWT principal to every request and background job.
4. Add composite tenant-aware foreign keys for all cross-entity relationships.
5. Add two-tenant API tests proving reads, writes, file access, refunds, disputes, exports, and audit history cannot cross tenant boundaries.
6. Move evidence files to private tenant-scoped object storage and isolate PayPal credentials per tenant.
7. Implement invitation lifecycle and granular RBAC with audited role changes.
8. Verify Alembic against PostgreSQL, frontend production build, Docker Compose, and deployment before cutover.

## Verification

- `python -m compileall -q app alembic tests`: passed.
- `python -m pytest -q`: **26 passed** (23 existing + 3 new tenant-foundation tests).
- PostgreSQL migration execution, RLS behavior against a live PostgreSQL instance, data backfill, Docker, frontend production build, and deployment: **not verified in this environment**.
