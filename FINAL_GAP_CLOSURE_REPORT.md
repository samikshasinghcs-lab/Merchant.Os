# MerchantOS final gap-closure report

Date: 12 November 2026

## Completed in this source package

- Tenant-scoped complaint clustering is exposed in Financial Operations. It supports optional local SentenceTransformer embeddings, optional hosted embeddings only after explicit external-processing opt-in, and deterministic TF-IDF cosine fallback. The response discloses method and states that similarity is not proof of cause.
- Financial AG Grid includes all requested case fields: case ID, type, customer, product, batch, order, amount, status, policy result, computed AI suggestion, evidence count, estimated net result, decision, and decider. Sorting, filtering, floating filters, quick search, status chips, CSV export, saved filters, and row-to-investigation selection are wired.
- Removed the private Bryntum scheduler package dependency and replaced the execution timeline with a native React read-only audit timeline. This avoids a private package/license/token blocking the web build.
- Added a canonical `run_resolution_pipeline` task to the Render workflow service configured by `render.yaml`; it performs deterministic anomaly, graph, policy-simulation and audit analysis and explicitly returns `financial_action: NONE`.
- Corrected the Render SDK import used by the case workflow dispatcher.
- Added private evidence storage path to the Render blueprint.
- Evidence upload is authenticated and tenant-scoped, validates MIME and file signature, enforces 5 MiB per file and 8 files per case, checks SHA-256 and perceptual duplicates, and uses a PostgreSQL advisory transaction lock around the per-case count check.
- Increased the request-body limit specifically for multipart evidence endpoints so the 5 MiB file limit is not accidentally blocked by the generic 2 MiB API cap.
- Added tests for clustering fallback and embedding paths, route-level principal dependencies, evidence count/body limits, and the deterministic Render pipeline.
- Added a provider preflight script and a provider verification runbook.

## Local verification run

- `python -m compileall -q app tests alembic workflows`: PASS.
- `pytest -q -rs`: 289 passed, 5 skipped.
- `node scripts/verify_frontend_syntax.cjs`: PASS (8 TS/TSX source files parsed).
- `node scripts/verify_financial_grid.cjs`: PASS (all 13 required financial grid columns and all 7 checked interactions present).
- Source checks for public-only frontend dependencies, Render workflow task, and Render evidence storage path: PASS.

### Why five tests were skipped

- One optional security test could not import `jose` in this local environment; `python-jose` is declared in `requirements.txt` and will be installed in CI.
- Two full API E2E tests require a deployed test URL, test token and order ID.
- One PayPal test requires a pre-reconciled, independently approved PayPal Sandbox approval plus explicit `SANDBOX_ONLY` confirmation.
- One Render test requires the deployed service URL, authenticated case ID and Render workflow configuration.

## Not honestly verifiable from this offline source environment

- Full frontend TypeScript typecheck and Vite production build: npm registry DNS is unavailable here, so dependencies could not be installed. The final GitHub Actions workflow runs `npm install`, syntax verification, grid verification, `tsc -b`, and `vite build` after upload.
- Live PostgreSQL migrations/RLS: requires a disposable PostgreSQL database. The optional `postgres-rls-smoke` workflow job is included.
- Actual PayPal Sandbox refund: requires the merchant's PayPal Sandbox credentials and an already reconciled, independently approved disposable Sandbox refund approval. The opt-in workflow test uses the existing approval/execution pathway and refuses to run without `MERCHANTOS_LIVE_REFUND_CONFIRM=SANDBOX_ONLY`.
- Actual Render workflow execution: requires the deployed Render workflow service, API key, service slug, callback URL and shared secret. The opt-in workflow test triggers the real case workflow and checks `/proof`.

## Safety boundary

No live PayPal action was performed while building this archive. No secrets were added. The existing maker-checker, capture reconciliation, policy digest, idempotency and Sandbox-only execution checks remain the only refund execution path.

## Release classification

**Competition demo candidate — backend and source-level frontend checks passed locally; frontend production build and live provider/database verification remain gated on GitHub Actions and merchant-owned Sandbox/Render resources.** Do not mark those external checks Verified or Live until their respective workflow jobs pass.
