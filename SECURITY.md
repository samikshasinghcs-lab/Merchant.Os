# MerchantOS security and tenancy status — v7.3.2

## Implemented in source

- JWT identity and active membership checks; short-lived access tokens and role checks from the database.
- Strict tenant-scoped request schemas for the `/api/v1/domain` API; client-supplied tenant IDs and server-owned status fields are rejected.
- Tenant-local SQLAlchemy session context using a bound, transaction-local PostgreSQL `set_config('app.tenant_id', ..., true)` value.
- Alembic revision `20261110_01` bootstraps the declared SQLAlchemy schema and enables + forces PostgreSQL RLS on 14 tenant-owned operational tables, with `USING` and `WITH CHECK` policies.
- Narrow SELECT-only token-hash policies for PayPal webhook route resolution and one-time invitation lookup; the application sets token-hash context transaction-locally and derives tenant context from the matched invitation row before updating it.
- A catalog-only RLS verification script: `python scripts/verify_postgres_rls.py`.
- Encrypted tenant PayPal credentials, signature-verified webhook intake, idempotent event inbox, bounded retry/dead-letter workflow and financial approval/execution separation.
- Optional review-cluster LLM explanation now wraps customer-authored reviews as bounded, provenance-labelled untrusted data; the call exposes no tools and model output remains advisory.
- Read-only MCP PayPal context tools; no refund/capture/write tool is exposed by MCP.

## Important: not production multi-tenant yet

The application still contains legacy business routes and intelligence modules backed by SQLite. They do not use the tenant-scoped PostgreSQL ORM repository layer. The PostgreSQL RLS policies protect the 14 PostgreSQL tenant tables only; they do not magically isolate legacy SQLite data, evidence files, static files, caches, or unrelated endpoints.

Keep `MULTI_TENANT_ENABLED=false`. Keep registration restricted to the configured single-merchant pilot. Do not onboard multiple real merchants until the legacy routes and storage have been migrated and tested end-to-end.

## PostgreSQL RLS operational requirements

- Run `alembic upgrade head` against the production PostgreSQL database before starting the app; the Docker API command does this before Uvicorn.
- The runtime role must not be a superuser and must not have `BYPASSRLS`. `FORCE ROW LEVEL SECURITY` subjects table owners to policy, but cannot constrain superusers or BYPASSRLS roles.
- The transaction-local tenant context must be derived from a verified active membership, never from browser input or model output.
- For Cloudflare Hyperdrive, set the context and query inside the same explicit transaction. Never use connection-level `SET` or assume session state survives Hyperdrive pooling.
- `scripts/verify_postgres_rls.py` verifies catalog state and role bypass flags only; it is not a substitute for two-tenant integration tests using the actual pooled runtime role.

## Cloudflare scope

This repository contains native PostgreSQL RLS policies and a Hyperdrive integration guide. It does not contain a deployed Cloudflare Worker, Wrangler configuration, Hyperdrive binding, Cloudflare Access configuration, R2/KV setup, or queue deployment. Those components must be reviewed separately if Cloudflare is added to the runtime.

## Remaining hard blockers

1. Migrate legacy SQLite business tables and every route/repository to tenant-scoped PostgreSQL access.
2. Run two-tenant PostgreSQL tests for SELECT/INSERT/UPDATE/DELETE, missing tenant context, role bypass, token-lookup exceptions, and connection-pool reuse.
3. Verify the actual deployed database role and apply the migration in the deployed environment.
4. Add MFA for financial approvals, token revocation/refresh rotation, distributed rate limiting and granular permissions.
5. Move evidence files to private tenant-scoped object storage with malware scanning and short-lived signed access.
6. Review data-processing terms and consent before sending merchant/customer review content to an external LLM.
7. Complete browser build, screenshot, responsive, keyboard, accessibility and runtime QA.
8. Complete an independent security assessment before production financial operations.

No claim of Cloudflare deployment, full application tenant isolation, prompt-injection immunity, formal compliance, penetration testing, or production certification is made.


## v7.3.2 security/privacy hardening

- Production readiness now rejects evidence storage at the web-served static root or anywhere beneath it, including a symlink used as the configured evidence directory.
- Existing evidence directories must not grant group/world permissions; the upload writer continues to enforce restrictive directory/file modes.
- Added regression tests for static-root, nested-static, and symlink path configurations.
- Added `.github/workflows/security-audit.yml` for dependency vulnerability auditing (`pip-audit`) and Python static analysis (`Bandit`). The workflow must pass on the actual GitHub branch before merge.
- See `docs/SECURITY_PRIVACY_ASSURANCE_v7_3_2.md` for the security/privacy control inventory and explicit non-production limitations.
