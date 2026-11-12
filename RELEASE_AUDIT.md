# MerchantOS competition handoff — implementation and verification audit

**Build date:** 12 November 2026  
**Scope:** single-merchant pilot / PayPal Sandbox only  
**Classification:** competition demo candidate; external provider and production deployment verification remains outstanding.

## What is in this build

- Unified workspace with operational pipeline, Proof navigation, signed-in user menu, environment disclosure, Render commit/uptime and computed/LLM configuration label.
- Financial Operations workspace with AG Grid, summary cards, search, sorting/filtering, CSV export and case selection.
- Case investigation with order/customer context, complaint messages, computed recommendation and reasons, expected-loss comparison, policy check, private evidence upload/preview, disposition/P&L, sticky reason-gated human decision, audit history, workflow dispatch and PayPal execution status.
- Deterministic policy rules for return window, one exchange, opened hygiene items, refund cap and cancellation before shipping. Failed rules can only be overridden with a reason; override is audited.
- COGS and cost entry, configurable recovery percentages, repair/supplier credit/write-off handling, estimated net recovery and product/batch/reason/week roll-ups. Payment fee values remain merchant-entered; no claim is made about PayPal fee refunds.
- Batch complaint-rate lift and two-sided Fisher exact p-value, repeat-returner signals, descriptive customer/product/batch z-scores and charts. All statistical interpretation is labelled exploratory and non-causal.
- Complaint clustering supports hosted embeddings only when explicitly enabled with the required privacy acknowledgement; TF-IDF cosine similarity is the local fallback.
- Evidence checks include MIME allow-list, file signature, 5 MB limit, 8 files per case, SHA-256 duplicate detection, perceptual image hash comparison and private-disk storage.
- PayPal refunds remain in the existing separate reconciliation, maker-checker approval and execution pathway. The case decision endpoint never moves money.
- Render workflow dispatch calls `run_resolution_pipeline`, persists the returned run ID and displays it in case detail/Proof when configured.
- `/api/health` reports liveness, environment, service, commit and process uptime. `/proof` reports latest provider execution, workflow reference, audit entries and disclosures.
- Database-level append-only guards now block UPDATE/DELETE of audit rows in SQLite and PostgreSQL. PostgreSQL RLS remains tenant-scoped.

## Verification performed in this build environment

| Check | Result | Evidence / boundary |
|---|---|---|
| Python compilation | PASS | `python -m compileall -q app tests alembic` |
| Backend tests | PASS | `pytest -q`: **267 passed, 3 skipped** |
| Append-only audit guard | PASS | New SQLite test confirms UPDATE/DELETE rejected and INSERT allowed |
| Frontend TS/TSX syntax parse | PASS | 8 source files parsed with TypeScript compiler; zero syntax diagnostics |
| Frontend dependency install | BLOCKED | `npm install --package-lock-only` timed out in this environment |
| Frontend typecheck | NOT VERIFIED | React/Vite dependencies unavailable locally |
| Frontend production build | NOT VERIFIED | React/Vite dependencies unavailable locally |
| Alembic full upgrade | BLOCKED LOCALLY | Runtime lacks `passlib`; it is declared in `requirements.txt`. Run migration in CI/deployment environment after dependency installation. |
| PostgreSQL RLS + append-only trigger | NOT VERIFIED LIVE | SQL migration is present; no PostgreSQL service was available here |
| PayPal Sandbox refund | NOT VERIFIED LIVE | Requires merchant Sandbox app credentials, a captured Sandbox payment and a configured approval/execution test |
| Render deployment/workflow | NOT VERIFIED LIVE | Requires deployed Render service, API key, workflow service slug and provider run confirmation |
| Mobile device layout | NOT VERIFIED ON DEVICE | Responsive single-column/sticky decision styles and contained grid are implemented; verify on the actual demo phone |

The GitHub Actions workflow installs frontend dependencies with `npm install` because this repository snapshot has no lockfile, then runs syntax parsing, typecheck and production build. A lockfile should be generated and committed when registry access is available; until then dependency resolution is not fully reproducible.

## A–K acceptance status

Legend: **Implemented** = source path exists; **Locally verified** = automated checks passed here; **Live verified** = deployed/provider behavior was observed. These are deliberately separate.

| Area | Implementation status | Verification boundary |
|---|---|---|
| A — Global layout | Implemented | Device-level mobile check and live provider badge confirmation remain. Unknown provider state is shown as unconfirmed rather than a false green check. |
| B — Cases grid | Implemented | AG Grid, summary cards, requested columns, quick search, sort/filter, CSV and row selection exist. Saved filters are optional. Frontend typecheck/build still pending. |
| C — Case detail | Implemented | Case-specific evidence is linked through immutable lifecycle events; decision requires evidence, reason and note. Human approval is a proposal, not a payment action. Frontend build and provider demo remain pending. |
| D — Policy engine | Implemented | Deterministic rules and audited reasoned override exist. Inputs are explicitly disclosed as merchant-supplied and must be checked against source order/fulfilment records. |
| E — Profit/loss | Implemented for estimates and roll-ups | COGS, recovery rates, repair, supplier credit, refund, shipping, handling, fee input and write-off are calculated. Actual inventory movement and final ledger realization require connected warehouse/provider evidence. |
| F — Insights | Implemented | Fisher exact, lift, repeat-returner, cost-by-reason, batch-loss and weekly case charts exist. Results are exploratory; no causal claim. |
| G — AI/deep tech | Implemented as computed decision support plus optional clustering | Case recommendation is deterministic/computed, not a calibrated probability. Embeddings require explicit privacy configuration; TF-IDF fallback exists. Z-score and pHash checks exist. No accuracy claims. |
| H — PayPal | Existing guarded pathway preserved and case-linked | Sandbox end-to-end refund and provider-confirmed status not tested here. Live mode remains prohibited by readiness/execution controls. |
| I — Render | Implemented | Health metadata and workflow dispatch/run persistence exist. Actual Render uptime, logs and run ID require deployment verification. |
| J — Proof page | Implemented | Authenticated `/proof` page/API exists. It reports unknown/missing values explicitly; live evidence requires deployment. |
| K — Security/audit | Implemented on financial lifecycle paths | Tenant-scoped auth, role checks, maker-checker transition, private evidence limits and DB append-only guards exist. Full audit of every legacy route and live PostgreSQL RLS test remain release gates. |

## Non-negotiable behavior

1. AI recommends; deterministic code validates; humans authorize.
2. No live-money execution in a competition demonstration. Use PayPal Sandbox only.
3. Financial inputs disclose their source; estimates and realized outcomes stay separate.
4. Statistical correlation is never presented as proven causation.
5. No unmeasured AI accuracy claims.
6. UI and proof materials distinguish Implemented, Verified and Live.

## Release gates before claiming fully verified/live

1. Run GitHub Actions and obtain a passing frontend typecheck/build.
2. Apply Alembic migrations against a disposable PostgreSQL database and test tenant A/B isolation plus append-only triggers.
3. Configure PayPal Sandbox, create/capture a test payment, reconcile it, obtain independent approval, execute an idempotent refund and verify the provider refund ID/status.
4. Configure Render Workflows, invoke `run_resolution_pipeline`, verify the returned run ID and inspect Render logs.
5. Verify `/api/health` and `/proof` on the deployed service; collect screenshots with Sandbox/demo disclosures.
6. Review legacy endpoint authentication and webhook signature exceptions before any public deployment.

## Safety

Do not commit `.env` files, credentials, tokens, customer data or private evidence. Do not enable PayPal live mode. This is a controlled single-merchant competition/pilot build, not a certification for general multi-tenant production SaaS.
