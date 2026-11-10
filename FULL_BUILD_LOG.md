# MerchantOS v0.1
**AI-assisted merchant back-office: feedback → transaction evidence → approved refunds → operational insight.**

Runnable hackathon MVP:
- 15 illustrative orders, 40 reviews, 5 illustrative dispute records
- deterministic complaint clustering
- exact order/customer matching for refund proposals
- human approval, per-refund and daily caps, duplicate-operation protection
- PayPal Sandbox refund adapter and safe demo mode
- evidence-grounded dispute drafts
- batch/category root-cause summaries and audit log
- browser dashboard

## Run
Python 3.10+:
```bash
python -m venv .venv
source .venv/bin/activate       # Windows: .venv\\Scripts\\activate
pip install -r requirements.txt
python seed/generate_seed.py
uvicorn app.main:app --reload
```
Open http://127.0.0.1:8000

## PayPal Sandbox checkout (Checkpoint 2)
Default `DEMO_MODE=true` simulates refund actions locally and blocks live checkout calls. To test the end-to-end Sandbox payment flow:

1. In the PayPal Developer Dashboard, create a **Sandbox REST app** and obtain its Sandbox client ID and secret.
2. Copy `.env.example` to `.env`; set `DEMO_MODE=false`, `PAYPAL_MODE=sandbox`, `PAYPAL_CLIENT_ID`, and `PAYPAL_CLIENT_SECRET`. Keep the secret on the backend only.
3. Start MerchantOS and create a test checkout:
   `POST /api/paypal/orders` with JSON such as `{"amount":"12.50","currency":"USD","product":"Test item","customer_name":"Sandbox Buyer"}`.
4. Open the returned `approval_url` and sign in using a **Sandbox personal/buyer** account (not your real PayPal account). Approve the payment.
5. Call `POST /api/paypal/orders/{merchant_order_id}/capture`. MerchantOS stores the PayPal order ID and the actual completed capture ID.
6. To test a refund, create a refund proposal only for a captured order, then approve it through the existing human-approval route. Use small Sandbox amounts.

The checkout routes are intentionally restricted to Sandbox, even when demo mode is disabled. Seed capture IDs are placeholders and cannot be refunded by PayPal. The automated tests mock PayPal responses; they verify our request/response handling, not a real external Sandbox transaction. A real Sandbox round-trip still requires your Developer app credentials and buyer approval.

## Safety
AI does not move money. A merchant approves; deterministic backend checks payment status, amount, per-refund cap, daily cap and remaining captured value. PayPal response is authoritative. Demo actions are labelled simulated. Dispute records in the seed are illustrative local examples, not real PayPal disputes. Drafts are not submitted. Matching requires exact customer and order references. This is not escrow and is not production-ready.

Before production add authentication, tenant isolation, encrypted secret storage, webhook signature verification, database migrations, concurrency-safe refund reservation, rate limits, monitoring and compliance review.

## API
`POST /api/paypal/orders`, `POST /api/paypal/orders/{merchant_order_id}/capture`,
`GET /api/dashboard`, `/api/clusters`, `/api/clusters/{id}`, `POST /api/analyze`,
`GET /api/refunds`, `POST /api/refunds/propose`,
`POST /api/refunds/{id}/approve`, `POST /api/refunds/{id}/reject`,
`GET /api/disputes`, `POST /api/disputes/{id}/draft`,
`GET /api/insights`, `GET /api/audit`, `GET /health`.

## Product principles
AI interprets. Deterministic systems validate. Humans authorize. PayPal executes. The audit system remembers.


## Checkpoint 1 status

See [docs/CHECKPOINT_1.md](docs/CHECKPOINT_1.md) and [docs/CHECKPOINT_2.md](docs/CHECKPOINT_2.md). Checkpoint 2 adds Sandbox order creation, buyer approval handoff, capture, capture-ID persistence, and idempotent repeat-capture handling. Automated PayPal tests use mocked responses; no real Sandbox transaction is claimed.

## Checkpoint 3 — Evidence Intelligence
Merchant-supplied evidence references can be registered against an existing order using `POST /api/evidence`. Query `GET /api/evidence?order_id=<id>` and assess a local dispute using `GET /api/disputes/{dispute_id}/assessment`. The assessment reports evidence-category coverage and gaps only; it does not authenticate evidence, predict outcomes, or submit material to PayPal. See `docs/CHECKPOINT_3.md`.


## Checkpoint 4 — Customer Resolution Intelligence

Checkpoint 4 adds deterministic customer-resolution triage and a human-managed resolution lifecycle.

- `GET /api/resolutions/recommendation/{review_id}` returns a category-based recommendation with rationale and an explicit no-financial-authorization flag.
- `GET /api/resolutions/message/{review_id}?tone=empathetic|concise` creates an editable customer message draft; it is never sent.
- `POST /api/resolutions` creates one active resolution per review.
- `GET /api/resolutions` lists resolution records; optional `status` filters the list.
- `PATCH /api/resolutions/{resolution_id}` moves a record through `OPEN`, `CONTACTED`, `RESOLVED`, or `ESCALATED`. `RESOLVED` and `ESCALATED` are terminal states.

Recommendations are rule-based triage, not legal advice or outcome predictions. Customer messages are drafts only. This checkpoint does not send messages, issue refunds, submit disputes, or authorize financial actions. Merchant review remains mandatory.

Run tests with `python -m pytest -q`.

## Checkpoint 5 — Root Cause Intelligence

The `GET /api/root-cause` endpoint aggregates observed complaint patterns by category, product, and batch. It reports completed refund outflow separately from a gross order-value exposure indicator for unresolved medium/high-severity complaints. The latter is **not** a predicted loss, refund liability, or savings estimate. Batch/product relationships are descriptive correlations and must not be treated as causal findings. See `docs/CHECKPOINT_5.md` for methodology and limitations.

## Checkpoint 6 — Trust & Accountability

The `/api/accountability` endpoint and dashboard panel expose operational indicators, resolution states, evidence registration coverage, payment statuses, currency-separated refund totals, and recent audit activity. MerchantOS deliberately does not generate a composite trust score. See `docs/CHECKPOINT_6.md` for methodology and limitations.

## Merchant Intelligence v2 (Checkpoint 7)
See `docs/CHECKPOINT_7_MERCHANT_INTELLIGENCE.md` for review CSV ingestion, export adapters, embedding/TF-IDF clustering, sentiment, optional LLM explanations, customer/transaction investigation, matching tiers, configuration and limitations.

New endpoints include:
- `POST /api/reviews/import/{source}` (multipart CSV upload)
- `GET /api/reviews/imports`
- `GET /api/reviews/connectors`
- `POST /api/reviews/semantic-analysis`
- `GET /api/reviews/semantic-clusters`
- `GET /api/reviews/semantic-clusters/{cluster_id}/explanation`
- `GET /api/customers` and `GET /api/customers/{customer_id}`
- `GET /api/transactions/{order_id}`
- `GET /api/reviews/{review_id}/match-candidates`
- `POST /api/reviews/{review_id}/match`

## Checkpoint 8 — Evidence Vault & PayPal Dispute Intelligence

See `docs/CHECKPOINT_8_EVIDENCE_DISPUTES.md` for supported evidence files, SHA-256 integrity checks, PDF/image inspection, PayPal Sandbox dispute retrieval, response deadline tracking, human-approved evidence submission, endpoint details and limitations.

Key endpoints:
- `POST /api/evidence/upload?order_id=...&evidence_type=...&description=...`
- `GET /api/evidence/files?order_id=...`
- `GET /api/evidence/files/{file_id}/inspect`
- `POST /api/evidence/files/{file_id}/verify-integrity`
- `POST /api/paypal/disputes/sync`
- `GET /api/paypal/disputes`
- `GET /api/paypal/disputes/{dispute_id}`
- `POST /api/paypal/disputes/{dispute_id}/submit-evidence`

Evidence authenticity is **not** established by hashing or file inspection. Hashing detects byte changes after ingestion. The app is not authenticated and must not be publicly exposed with submission enabled until proper identity, authorization and tenant isolation exist. PayPal dispute calls are Sandbox-only and automated tests mock the provider; a real Sandbox dispute round-trip remains to be verified.


## PACT Commercial Trust Intelligence (Checkpoint 9)

See `docs/CHECKPOINT_9_PACT.md` for the agreement, scope-change, milestone evidence, mutual approval and PayPal Sandbox authorization/capture workflows. The extraction and evidence checks are deterministic baselines, not legal advice or proof of delivery. PayPal authorization is not escrow. Do not expose these endpoints publicly without authentication and tenant isolation.


## Checkpoint 10 — Frontend & infrastructure foundation
See `docs/CHECKPOINT_10_FRONTEND_INFRA.md` and `SECURITY.md`. Adds a React/TypeScript frontend, SQLAlchemy identity/workspace directory, JWT auth, basic role gates, Alembic migration, Docker Compose PostgreSQL/API/frontend stack and deployment scaffolding. **The business-domain store remains SQLite and this release is single-merchant only; multi-tenant isolation and production deployment are not complete.**

## Checkpoint 11 — tenant data foundation

The v1.1 checkpoint adds tenant-scoped SQLAlchemy models and a PostgreSQL RLS migration for the core merchant domain. This is a schema and isolation foundation only: legacy business routes still use SQLite, so multi-merchant production mode remains disabled. See `docs/CHECKPOINT_11_TENANT_DATA_FOUNDATION.md` and `SECURITY.md` before deployment.

## v1.2 completion & hardening checkpoint

See `docs/CHECKPOINT_12_COMPLETION_HARDENING.md`. This checkpoint adds authenticated tenant-scoped PostgreSQL order/review APIs, fail-closed PayPal webhook signature verification and Fernet credential-encryption primitives. It does **not** complete migration of legacy SQLite routes, per-merchant PayPal credential storage, authenticated PACT signatures, durable webhook processing, production deployment or external verification. Single-workspace registration remains intentionally enforced.


## v1.3 operational security additions

This checkpoint adds tenant-owned encrypted PayPal credential records, verified-webhook inbox records, invitation primitives and identity-bound PACT approval records. See `docs/CHECKPOINT_12_COMPLETION_HARDENING.md` for exact boundaries and external blockers. These additions do not yet make legacy SQLite workflows multi-tenant or production-ready.
