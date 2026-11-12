# MerchantOS competition completion — final implementation and verification report

Date: 12 November 2026

## Implemented in this update

- Tenant-scoped complaint clustering endpoint and UI panel.
- TF-IDF/cosine similarity is the default local fallback.
- Optional local sentence-transformer embeddings (`MERCHANTOS_LOCAL_EMBEDDINGS=true`). Install `requirements-embeddings.txt` to enable this optional mode.
- Hosted embeddings are disabled unless `MERCHANTOS_ALLOW_EXTERNAL_REVIEW_PROCESSING=true`; production readiness additionally requires external-processing DPA/redaction acknowledgements.
- Deterministic tenant review cluster IDs are persisted and an audit event is recorded.
- Case AG Grid includes all 13 requested columns, sorting/filtering, quick search, status chips, row investigation, CSV export, and saved filters.
- Added a source-level AG Grid acceptance verifier.
- Every financial lifecycle API route requires the authenticated principal dependency.
- Evidence upload enforces 8 files per case and 5 MiB per file; unit tests cover the boundaries. PostgreSQL advisory transaction locking prevents parallel uploads racing past the per-case count.
- Added opt-in live Render workflow and PayPal Sandbox smoke tests. The PayPal test can execute exactly one already independently approved Sandbox refund and requires explicit `SANDBOX_ONLY` confirmation.
- Added optional PostgreSQL migration, RLS catalog, and two-tenant row-isolation checks to manual GitHub Actions.
- Existing PayPal maker-checker, capture reconciliation, idempotency, and Sandbox-only execution path is retained.

## Local verification performed

| Check | Result |
|---|---|
| Python compilation (`app`, `tests`, `alembic`, `scripts`) | PASS |
| Backend tests | **289 passed, 5 skipped** |
| Frontend TypeScript/TSX syntax | PASS — 8 source files |
| Financial AG Grid acceptance verifier | PASS — 13 columns and 7 interactions |
| App route registration | PASS — 132 routes; key financial, clustering, proof, workflow and PayPal routes present |
| GitHub Actions YAML parse | PASS — 4 jobs |

The five skipped tests are: one optional security-hardening test because `python-jose` is absent from this local runtime (the CI job installs `requirements.txt`); two configured API E2E tests without a live base URL/token/order ID; one PayPal Sandbox execution test without the explicit confirmation and pre-approved approval ID; and one Render workflow test without live URL/token/case ID.

## Not verified locally or live

| Check | Status | What is required |
|---|---|---|
| Frontend TypeScript typecheck and Vite production build | NOT VERIFIED | npm dependency installation timed out in this environment. The global `tsc` run cannot resolve React/Vite declarations without `node_modules`. GitHub Actions is configured to install, typecheck, and build. |
| PostgreSQL migration and real RLS isolation | NOT VERIFIED LIVE | A disposable PostgreSQL database, restricted non-superuser/non-BYPASSRLS role, two existing tenant IDs, and rows for both tenants. Manual workflow applies migrations, checks RLS catalog and performs read isolation checks. |
| PayPal Sandbox refund | NOT VERIFIED LIVE | Sandbox credentials, captured Sandbox payment, reconciled refund request, independent approver token, server-side `PAYPAL_EXECUTION_ENABLED=true`, and explicit `SANDBOX_ONLY` confirmation. |
| Render workflow | NOT VERIFIED LIVE | Deployed Render Workflow service, `RENDER_API_KEY`, `WORKFLOW_SERVICE_SLUG`, authenticated token, and eligible case ID. |

## One-shot external verification procedure

1. Configure Render production-pilot environment variables: `AUTH_REQUIRED=true`, strong `JWT_SECRET_KEY`, `DEMO_MODE=false`, `PAYPAL_MODE=sandbox`, PostgreSQL identity DB, persistent private evidence storage, and the single-tenant pilot acknowledgement. Keep live PayPal mode unsupported.
2. For the Sandbox competition test only, configure the tenant's PayPal Sandbox credentials and set `PAYPAL_EXECUTION_ENABLED=true` after the approval/reconciliation controls are confirmed. The execution adapter rejects live mode.
3. Create a Sandbox payment and capture it. Create a refund approval, reconcile against PayPal's canonical capture read, and have a different authorized user approve it.
4. Add GitHub Actions repository secrets (never commit them): `MERCHANTOS_LIVE_BASE_URL`, `MERCHANTOS_LIVE_TOKEN`, `MERCHANTOS_LIVE_CASE_ID`, `MERCHANTOS_LIVE_APPROVAL_ID`, and `MERCHANTOS_LIVE_REFUND_CONFIRM=SANDBOX_ONLY`.
5. For PostgreSQL verification also add `POSTGRES_RLS_DATABASE_URL`, `POSTGRES_RLS_TENANT_A_ID`, and `POSTGRES_RLS_TENANT_B_ID`. Use a disposable verification database and a restricted application runtime role; both tenants need at least one order row.
6. Open Actions → MerchantOS final acceptance checks → Run workflow. Select `run_live_provider_smoke` only when intentionally executing one Sandbox refund and one Render workflow. Select `run_postgres_rls_smoke` only against the disposable verification database.
7. Save the passing CI run URL, Sandbox refund ID/status, Render run ID/URL, `/api/health`, `/api/v1/financial-lifecycle/proof`, and PostgreSQL RLS output as competition evidence.

## Status semantics and safety

- Implemented = code exists. Verified = automated test evidence exists. Live = deployed provider/service behavior confirmed.
- AI/clustering is advisory; deterministic policy checks and humans control decisions.
- Complaint clusters are similarity groups, not proof of a shared cause.
- PayPal remains maker-checker, capture-reconciled, idempotent and Sandbox-only.
- The live Sandbox test is opt-in because it executes a Sandbox refund. No live-money execution is supported.
