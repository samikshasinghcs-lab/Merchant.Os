# MerchantOS

> **v7.3.2 security/privacy hardening checkpoint:** Production readiness now rejects evidence-upload paths that resolve to or sit beneath the web-served static directory, rejects a symlink as the configured evidence directory, and checks restrictive permissions on an existing evidence directory. See [`docs/SECURITY_PRIVACY_ASSURANCE_v7_3_2.md`](docs/SECURITY_PRIVACY_ASSURANCE_v7_3_2.md) for implemented controls, limitations, and deployment requirements. A dedicated GitHub Actions security audit runs dependency vulnerability and Bandit static analysis.

**From complaint to refund.** MerchantOS reads a seller's customer reviews, matches each complaint to the real PayPal order behind it, and proposes a refund. The merchant approves, PayPal executes, and every step is written to an audit log. It then shows which batch or product is behind the complaints.

Built for the PayPal AI Hackathon 2026.

## The problem
A small seller gets hundreds of reviews and a trickle of PayPal disputes. Complaints sit in one place, payments in another, and nobody connects them. Refunds are slow, disputes get lost, and the cause (a bad batch, a weak box) never gets found.

## What it does
1. **Reads reviews** and groups them into complaint clusters (damaged packaging, leakage, late delivery, quality).
2. **Matches** each complaint to an order using an exact customer + order reference. Weak matches are never auto-proposed.
3. **Proposes refunds** for matched, captured orders. Nothing moves without a human click.
4. **Pays through PayPal.** Approved refunds call the PayPal Orders and Payments APIs (Sandbox).
5. **Finds root causes** by batch and product, and drafts evidence-based replies to disputes.

> AI interprets. Code validates. Humans authorize. PayPal executes. The audit log remembers.

## Verified against PayPal Sandbox
On 10 Nov 2026 the full loop was run through this app against the PayPal Sandbox: order created, approved by a Sandbox buyer, payment captured, refund proposed from a customer complaint, approved by the merchant, and refunded by PayPal. The refund appears in the Sandbox account activity.

## Safety rules (enforced in code)
- The AI never moves money. A merchant approves every refund.
- Per-refund cap and daily cap; a refund can never exceed the captured amount.
- Duplicate-operation protection (idempotency keys); repeat approvals do nothing.
- PayPal's response is the source of truth. Demo actions are labelled as simulated.
- PayPal calls are Sandbox-only in this release.

## Run it
Python 3.10+:
```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python seed/generate_seed.py
uvicorn app.main:app --reload
```
Open http://127.0.0.1:8000. By default it runs in **demo mode**: refunds are simulated locally and no PayPal call is made.

### Live PayPal Sandbox
1. In the PayPal Developer Dashboard, create a Sandbox app and copy its client ID and secret.
2. Copy `.env.example` to `.env` and set `DEMO_MODE=false`, `PAYPAL_MODE=sandbox`, `PAYPAL_CLIENT_ID`, `PAYPAL_CLIENT_SECRET`. Keep the secret on the backend only.
3. Create a checkout: `POST /api/paypal/orders` (try it from http://127.0.0.1:8000/docs) with `{"amount":"12.50","currency":"USD","product":"Test item","customer_name":"Sandbox Buyer"}`.
4. Open the returned `approval_url` and pay with a **Sandbox personal (buyer)** account. Never use a real account.
5. Capture: `POST /api/paypal/orders/{merchant_order_id}/capture`.
6. Add a review for that order, run **Analyze feedback**, open the cluster, and propose and approve the refund from the dashboard.

Seeded demo orders carry placeholder capture IDs, so only orders you capture yourself can be refunded in live mode.

## How the analysis works
- Complaint clusters use deterministic keyword rules, so results are explainable and repeatable.
- An optional semantic analysis (embeddings, with a TF-IDF fallback) and optional LLM cluster explanations are available when an OpenAI-compatible key is configured. Without a key, a computed summary is returned and labelled as not LLM-generated. See `docs/CHECKPOINT_7_MERCHANT_INTELLIGENCE.md`.
- Root-cause findings are descriptive correlations, not proven causes.

## Tests
```bash
python -m pytest -q
```
PayPal and LLM calls are mocked in tests. The live Sandbox flow above was verified manually.

## Limits (what this is not)
A hackathon pilot prototype, not production software. The React workspace has an identity/login foundation, but registration is deliberately restricted to one merchant pilot. Most legacy business workflows still use SQLite; the PostgreSQL tenant-domain and operational-security work is a foundation, not a completed cutover of those workflows. Do not enable additional merchant workspaces or expose the service publicly with live PayPal credentials. See `SECURITY.md`, `docs/CHECKPOINT_11_TENANT_DATA_FOUNDATION.md`, `docs/CHECKPOINT_12_COMPLETION_HARDENING.md`, and `docs/FULL_BUILD_LOG.md`.

## What's next
Growth insights for sellers, payment anomaly monitoring, per-merchant credentials, and moving the main workflow onto the tenant-isolated database.

## Stack
Python, FastAPI, SQLite, PostgreSQL tenant-foundation, SQLAlchemy, Alembic, React, TypeScript, Vite, scikit-learn, PayPal REST APIs (Orders v2, Payments, Disputes). MIT licensed.

## Phase 1 — PayPal integration & judging foundation

Phase 1 adds Sandbox adapters and backend routes for PayPal Invoicing v2, Transaction Search v1 and Payment Method Tokens v3 (PayPal Wallet setup-token flow). See `docs/PHASE_1_INTEGRATION_AND_JUDGING.md` for endpoint scope, OAuth permissions, guardrails, sponsor-tool status and the five judging criteria evidence plan.

New endpoints:
- `GET /api/paypal/capabilities` — integration inventory and environment state.
- `POST /api/paypal/invoices` — create a draft invoice (does not notify the payer).
- `GET /api/paypal/invoices/{invoice_id}` — retrieve invoice state.
- `POST /api/paypal/invoices/{invoice_id}/send` — send only with explicit merchant confirmation.
- `GET /api/paypal/transactions` — bounded Transaction Search query (maximum 31 days).
- `POST /api/paypal/vault/setup-tokens` — start a customer-consented PayPal Wallet vaulting flow.
- `POST /api/paypal/vault/payment-tokens` — finalize a PayPal-approved setup token after explicit merchant confirmation.

Set `PUBLIC_APP_URL` to the HTTPS public base URL when using the Vault redirect flow. These routes are Sandbox-only and remain disabled while `DEMO_MODE=true`. PayPal app permissions/scopes must be enabled in the PayPal Developer Dashboard. The Vault adapter does not accept or store card PAN/CVV. Token lifecycle persistence and multi-tenant credential routing remain future work.

### Optional read-only MCP server

Install the separate MCP extra and configure Sandbox credentials:

```bash
pip install -r requirements-mcp.txt
DEMO_MODE=false PAYPAL_MODE=sandbox python -m app.mcp_server
```

The local stdio MCP server exposes the PayPal API catalogue plus read-only transaction, invoice and dispute lookups. It deliberately has no financial write tools. Do not expose it on an unauthenticated network transport.

### Postman verification

Import `integrations/postman/MerchantOS-PayPal-Sandbox.postman_collection.json`. Configure `baseUrl` and a bearer `accessToken`. The collection computes a rolling seven-day UTC window for Transaction Search. Run against a configured Sandbox app; do not interpret a collection file as proof that the external PayPal service has been tested.


## Sponsor tooling activation

The project now includes source-level integrations for Render Workflows, AG Grid Community and Bryntum Scheduler Community. The APIMatic PayPal Context Plugin has a one-command activation script for supported coding-agent environments. See [`docs/SPONSOR_TOOL_ACTIVATION.md`](docs/SPONSOR_TOOL_ACTIVATION.md) for setup, required secrets, installation and verification. Cloud workflow release and local npm dependency installation must still be completed in an authenticated developer/deployment environment.

## Phase 3 — Deterministic financial controls

Phase 3 adds tenant-scoped refund approval envelopes, decimal-safe deterministic refund policy checks, canonical-payload digests, and maker-checker approval. New requests remain `PENDING_RECONCILIATION` until an internal trusted PayPal adapter calls `record_canonical_capture_reconciliation`; client-submitted provider status is never accepted as proof. Approval does not itself execute a PayPal write. See `docs/PHASE_3_IMPLEMENTATION.md`.

## Phase 3 — Deterministic financial controls

Phase 3 adds tenant-scoped refund approval envelopes, decimal-safe deterministic refund policy checks, canonical-payload digests, and maker-checker approval. New requests remain `PENDING_RECONCILIATION` until an internal trusted PayPal adapter calls `record_canonical_capture_reconciliation`; client-submitted provider status is never accepted as proof. Approval does not itself execute a PayPal write. See `docs/PHASE_3_IMPLEMENTATION.md`.

## Phase 4 — tenant-aware Sandbox execution

Phase 4 adds a dedicated tenant-credential PayPal adapter and a durable, tenant-isolated refund execution ledger. An independently approved refund can be executed only by its recorded approver, only against PayPal Sandbox, and only when `PAYPAL_EXECUTION_ENABLED=true` is explicitly set. The default remains disabled. Provider timeouts are recorded as `UNKNOWN` and are never automatically retried. See `docs/PHASE_4_IMPLEMENTATION.md`.

## Phase 5 — Dispute Intelligence & Evidence Operations

Phase 5 adds deterministic PayPal dispute deadline monitoring and evidence-package readiness checks. It verifies requested evidence types, order linkage, transaction identifiers when available, file ownership, MIME/size limits and file integrity before a human reviews a submission. It also records ambiguous PayPal submission outcomes as `UNKNOWN` and blocks blind duplicate submissions. See `docs/PHASE_5_IMPLEMENTATION.md` for API details and limitations. Dispute records remain in legacy SQLite storage and are not yet tenant-isolated; do not expose the legacy dispute routes unauthenticated or treat this checkpoint as production-ready multi-tenant dispute handling.

---

## DeepTech Intelligence & Assurance Layer (experimental)

MerchantOS now includes an isolated `app/deeptech/` package with deterministic engineering primitives for:

- Canonical transaction fingerprints (SHA-256 and optional HMAC).
- Merchant/currency-local robust anomaly scoring with human-readable signals.
- Exact-identifier transaction relationship graphs and graph metrics.
- Seeded Monte Carlo financial scenario simulation.
- Observational association screening with explicit non-causality caveats.
- Tamper-evident hash-chain audit prototypes.
- Model evaluation, probability calibration, temporal splits, feature drift, model cards, and privacy-aware exports.

This layer is **experimental and advisory**. It does not authorize or execute payments, does not claim trained fraud AI, and is not a production digital twin. See [`docs/deeptech/ARCHITECTURE.md`](docs/deeptech/ARCHITECTURE.md) and [`docs/deeptech/DEMO_AND_VALIDATION.md`](docs/deeptech/DEMO_AND_VALIDATION.md).

Run its synthetic demonstration with `python -m app.deeptech.demo` and its tests with `python -m pytest -q`.
