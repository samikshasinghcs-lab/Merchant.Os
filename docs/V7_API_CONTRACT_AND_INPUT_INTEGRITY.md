# MerchantOS v7.0 — API Contract & Input Integrity

## Scope

This checkpoint hardens the authenticated tenant-scoped PostgreSQL domain API (`/api/v1/domain`). It does **not** complete the legacy SQLite migration or certify MerchantOS as a multi-tenant production service.

## Changes

- Added explicit Pydantic request contracts for tenant order and review creation.
- Unknown fields are rejected (`extra=forbid`), preventing clients from assigning server-owned fields such as `tenant_id`, `payment_status`, `category`, and `severity`.
- Order amounts must be finite, positive decimals with at most two fractional digits and fit the database precision (`Numeric(14,2)`).
- Currency input is normalized to uppercase and constrained to three alphabetic characters. This validates shape, not membership in a full ISO-4217 registry.
- Customer identifiers and names, product labels, and review text have explicit length bounds.
- Review ratings are strict integers from 1 to 5; string coercion is rejected.
- A review referencing an order now verifies that the order belongs to the authenticated tenant before creation. Missing or cross-tenant references return 404.
- Order creation no longer returns the internal tenant identifier in its response.

## Security properties and limitations

- Request schemas are input validation, not authorization. Tenant identity still comes only from the authenticated principal and the tenant-scoped database session.
- The order ownership check is application-level and uses a tenant predicate. PostgreSQL RLS remains an additional defense where the configured database role and migration are correctly applied.
- The check and subsequent review insert are separate transactions. If strict referential atomicity is required, add a composite tenant-aware foreign key and perform both operations in one transaction in a future migration.
- This checkpoint does not migrate legacy SQLite routes, implement full tenant isolation, add a global request-body byte limit, or prove PostgreSQL RLS against a live PostgreSQL server.
- No PayPal external calls, live-money execution, or production deployment were performed.

## Verification performed

- `python -m compileall -q app tests`: passed.
- `python -m pytest -q`: **92 passed, 1 skipped**.
- Added tests cover bounded monetary input, currency normalization, unknown/server-owned fields, review text and rating bounds, and cross-tenant order-reference rejection.
- The skipped test remains skipped by its existing environment/dependency condition; see pytest output for its exact reason when run in the target environment.
- Frontend production build and browser QA: not run.
- PostgreSQL migration/RLS integration, PayPal Sandbox round-trip, Render deployment, and independent penetration testing: not run.

## Release posture

MerchantOS v7.0 is a source-level API contract hardening checkpoint, **not a production-ready or multi-tenant SaaS release**. Maintain the single-merchant pilot restriction and keep financial execution disabled until the outstanding deployment and integration gates are independently verified.
