# MerchantOS v1.2 — Completion & Hardening Pass

## Added in this checkpoint

- Authenticated PostgreSQL tenant-domain API under `/api/v1/domain` for tenant-scoped order and review creation/listing and tenant-scoped domain summary.
- Tenant context is attached to each SQLAlchemy session and PostgreSQL RLS is applied by the existing migration.
- PayPal webhook signature verification utility calls PayPal's authoritative `/v1/notifications/verify-webhook-signature` endpoint and fails closed.
- Encrypted-secret primitives using Fernet and a separately configured `MERCHANTOS_CREDENTIALS_KEY`.
- Security tests for encryption round-trip, missing-key fail-closed behaviour and webhook verification fail-closed behaviour.

## Deliberately not represented as complete

The existing legacy business routes (dashboard, refunds, dispute centre, evidence, PACT and other operations) still use the legacy SQLite store. They are NOT yet migrated to PostgreSQL or tenant-scoped repositories. Registration therefore remains restricted to one workspace. Do not remove this restriction. The new `/api/v1/domain` endpoints are an isolated PostgreSQL tenant-scoped API foundation, not a full cutover of the product.

Per-merchant PayPal credential persistence and selection is not yet implemented; the current PayPal adapter still reads global environment credentials. The webhook endpoint verifies a supplied event but does not implement durable event inbox storage, deduplication, event processing or reconciliation. Verification requires real PayPal credentials, a configured webhook ID and network access.

PACT approvals still use the legacy agreement store and party-name workflow; they are not authenticated party signatures. Evidence files remain on the legacy local filesystem. Full RBAC remains incomplete; existing role gates are coarse. Production database migrations, Docker, frontend package installation/build, live PayPal round-trips, deployment, HTTPS, backup/restore and independent security assessment have not been run here.

## Verification

Run `python -m compileall -q app alembic` and `python -m pytest -q` in an environment with `requirements.txt` installed. Live service claims require separate runtime evidence.

## v1.3 implementation additions (code-level, not externally operational)

- Tenant-owned encrypted PayPal credential records by sandbox/live environment.
- Tenant-owned webhook inbox with event-ID uniqueness and RECEIVED state for idempotent intake.
- PayPal webhook verification routed against stored merchant webhook configurations.
- Tenant invitations with hashed one-time tokens, expiry, email binding and role allowlist.
- Identity-bound PACT approval records tied to agreement ID and version, with statement hash and duplicate approval prevention.
- New Alembic migration `0003_operational_security` and RLS policies for these records.
- Authenticated endpoints under `/api/v1/operations`.

## Remaining hard blockers (cannot be honestly closed without external infrastructure)

- The legacy business route family still uses SQLite and is not fully cut over to tenant-scoped PostgreSQL repositories. Multi-workspace registration remains restricted. The new tenant API and operations primitives do not make legacy refunds/disputes/evidence/PACT routes multi-tenant.
- Webhook processing currently persists verified events as RECEIVED; a worker, retry/dead-letter policy, and event-type-specific reconciliation handlers are required before payment state may be changed. The cross-tenant webhook credential lookup needs a dedicated least-privilege service DB role with RLS bypass or a separately designed routing registry in deployment.
- Invitation acceptance requires a controlled cross-tenant token lookup service role under forced RLS; do not enable invitations in production until configured and tested.
- PACT authenticated approval records are an identity-backed parallel record; legacy PACT agreement state is not yet transactionally linked to these records.
- Per-merchant PayPal credential records are encrypted at rest, but key rotation, managed KMS/HSM, credential health checks and live PayPal calls remain external operational work.
- No claim of production deployment, live PayPal verification, PostgreSQL migration execution, frontend build, independent audit, independent evidence authenticity, or penetration testing is made.
