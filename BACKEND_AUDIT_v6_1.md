# MerchantOS Backend Audit — v6.1

Audit date: 10 November 2026  
Scope: source inspection and local automated checks of the v6.1 project tree. No external PayPal or Render calls were made during this audit.

## Verification performed

- `python -m pytest -q`: **73 passed**.
- `python -m compileall -q app tests`: **passed**.
- Reviewed API route inventory, auth middleware, tenant operations, PayPal adapters, refund approval/execution services, webhook ingestion/processing, release readiness checks, and deployment/security documentation.

Passing unit tests do not establish that external PayPal/Render integrations work. The tests predominantly mock provider calls. No live Sandbox round-trip was repeated as part of this audit.

## Findings

### F-01 — Refund approval workflow has a dead-end reconciliation transition

**Severity: Critical for the intended refund workflow**

`POST /api/v1/operations/financial/refund-approvals` creates requests in `PENDING_RECONCILIATION`. The only implementation that advances a request to `PENDING_APPROVAL` is `record_canonical_capture_reconciliation()` in `app/financial_approval_service.py`. A repository-wide search shows this function is not called by any API route, workflow handler, or adapter. Consequently, requests created through the exposed API cannot reach the approval state through the current application flow. The execute endpoint is therefore unreachable through the normal lifecycle.

**Remediation implemented in v6.2:** added `POST /api/v1/operations/financial/refund-approvals/{approval_id}/reconcile`. The endpoint fetches the request by tenant, constructs the tenant-bound Sandbox PayPal adapter, reads the canonical capture server-side, and invokes deterministic policy evaluation. No provider facts are accepted from the request body. Only a `COMPLETED` capture is eligible for automatic reconciliation: PayPal's capture GET does not expose a reliable cumulative refund amount, so `PARTIALLY_REFUNDED`, `REFUNDED`, pending, and unknown statuses are blocked rather than guessed. Daily cap accounting uses the MerchantOS execution ledger (including reserved/unknown outcomes) for the current UTC day and currency. It does **not** include refunds made outside MerchantOS; this limitation is returned in the audit documentation and must be resolved with an authoritative merchant-wide ledger before broad production use. Added tests cover completed capture, partial-refund fail-closed behavior, and provider failure preserving `PENDING_RECONCILIATION`.

### F-02 — PostgreSQL tenant-domain foundation is not the active merchant application data path

**Severity: High / release-scope limitation**

The legacy business routes in `app/main.py` continue to use SQLite (`app/db.py`) for orders, reviews, refunds, evidence, disputes, agreements, milestones, and audit. The newer `/api/v1/domain` endpoints use PostgreSQL and tenant-scoped SQLAlchemy models, but they are a separate limited API surface. `SECURITY.md` and `README.md` correctly disclose that this is not a completed multi-tenant migration.

**Required fix:** either keep the app explicitly single-merchant pilot-only, or migrate every business workflow, query, background task, evidence object, and audit event to tenant-scoped storage before enabling multiple merchants.

### F-03 — External PayPal and Render integrations are not proven by the automated suite

**Severity: High / evidence gap**

The tests pass, but PayPal and workflow tests use mocked provider behavior. The checked-in `RELEASE_TEST_REPORT.txt` says external integration tests were not run in the release build. The README describes a manual Sandbox loop as verified on 10 November 2026, but this audit did not independently reproduce it.

**Required fix:** run and capture a fresh PayPal Sandbox test covering order create, buyer approval, capture, canonical capture read, refund request, provider response retrieval, and webhook signature verification. Separately verify Render Workflow dispatch and authenticated callback behavior.

### F-04 — Deployment authentication depends on environment configuration

**Severity: High if misconfigured; guarded by release readiness**

`.env.example` defaults `AUTH_REQUIRED=false`. The API middleware enforces bearer authentication only when `AUTH_REQUIRED=true`. The production readiness checker requires authentication, a strong JWT secret, Sandbox-only configuration, persistent storage, workflow credentials, and other deployment gates. Docker Compose sets authentication on, but any alternate deployment must preserve that setting.

**Required fix:** ensure every public deployment sets `APP_ENV=production` and `AUTH_REQUIRED=true`; test the deployed configuration rather than relying only on local defaults.

### F-05 — Financial execution is deliberately disabled by default

**Severity: Intentional guardrail; workflow incomplete until F-01 is fixed**

`PAYPAL_EXECUTION_ENABLED` defaults to false, the execution service rejects non-Sandbox environments, and the release readiness checker requires execution to remain disabled for this release candidate. The execution service reserves an idempotent ledger row before provider I/O and treats ambiguous outcomes as `UNKNOWN` without blind retries. This is a useful safety design, but it is not evidence that the end-to-end execution lifecycle is complete.

**Required fix:** do not enable this flag until reconciliation is wired, the Sandbox lifecycle is independently verified, and failure/replay behavior is tested. Keep live-money execution disabled.

### F-06 — Legacy merchant workflows remain broader than the tenant-isolated API surface

**Severity: High for multi-tenant/public use**

The project intentionally limits registration to one workspace while legacy tables lack tenant IDs. This restriction is appropriate for the current pilot. It must not be removed based solely on the existence of tenant-aware identity tables or the `/api/v1/domain` routes.

**Required fix:** maintain the single-workspace restriction and add a deployment-level check/monitor for accidental second-tenant registration until migration and cross-tenant isolation tests are complete.

## Current assessment

- **Local backend test suite:** green (73/73).
- **Python compilation:** green.
- **Refund approval lifecycle:** reconciliation route is now wired in v6.2; partial-refund history and external-to-MerchantOS daily activity remain fail-closed/limited as documented.
- **Tenant isolation of the complete merchant application:** incomplete; pilot-only.
- **PayPal/Render external integration evidence:** not independently verified in this audit.
- **Live-money readiness:** not ready and intentionally disabled.

## Recommended next implementation sequence

1. Complete authoritative merchant-wide refund-history/daily-cap reconciliation, including refunds initiated outside MerchantOS.
2. Add focused tests around the complete request → reconcile → maker/checker approval → Sandbox execution lifecycle, including ambiguity and duplicate cases.
3. Review legacy route authorization and single-tenant enforcement against the actual deployment configuration.
4. Perform a fresh external Sandbox and Render integration verification and record request IDs/statuses with secrets and personal data redacted.
5. Only then proceed to broader tenant-domain migration and frontend integration.
