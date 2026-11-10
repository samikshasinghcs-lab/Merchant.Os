# MerchantOS — Phase 5: Dispute Intelligence & Evidence Operations

## Delivered

- Deterministic response-deadline monitor with overdue, 6-hour, 24-hour, 3-day and upcoming states.
- Evidence readiness preflight endpoint. It checks PayPal's current `WAITING_FOR_SELLER_RESPONSE` state, seller-requested evidence types, manual order link, transaction identifier match (when PayPal supplies identifiers), file ownership/order match, supported MIME types, individual and aggregate size limits, and SHA-256 integrity verification.
- Explicit human-review requirement and a disclaimer that completeness checks do not prove truth, authenticity, legal sufficiency or likely dispute outcome.
- Safer ambiguous-outcome handling for PayPal evidence submissions: network timeouts and provider 5xx responses are stored as `UNKNOWN`, not `FAILED`; duplicate packages in `UNKNOWN` state are blocked from blind resubmission.
- Existing PayPal Sandbox-only submission restriction and explicit human confirmation remain in place.

## API

- `GET /api/paypal/disputes/deadlines` — deadline dashboard for locally synced disputes.
- `POST /api/paypal/disputes/{dispute_id}/evidence-readiness` — body: `{"merchant_order_id":"...","file_ids":["..."]}`. This is a read/preflight operation; it does not submit evidence.
- `POST /api/paypal/disputes/{dispute_id}/submit-evidence` — existing explicit confirmation path; it remains Sandbox-only.

## Safety boundaries and known limitations

- Disputes are still stored in the legacy SQLite domain tables. This phase does not claim tenant-isolated dispute storage or PostgreSQL RLS for these records.
- The legacy dispute sync/submission routes use the configured application-level PayPal credentials. A per-tenant dispute credential adapter and full tenant-scoped domain migration remain required before multi-tenant production use.
- The `human_approved` request field is an explicit workflow confirmation, not a cryptographic signature or substitute for authenticated maker-checker approval. Keep `AUTH_REQUIRED=true` and enforce OWNER/ADMIN access in a deployed environment; the legacy routes should not be exposed unauthenticated.
- `UNKNOWN` submissions require an operator to refresh the PayPal dispute and reconcile the provider's current state. There is deliberately no automatic retry.
- A hash match establishes byte integrity since registration only; it does not authenticate the evidence or validate its claims.
- PayPal Sandbox end-to-end submission and real deadline behavior still require credentials and an actual Sandbox dispute with seller-response actions.

## Verification

- Full local test suite: 69 passed.
- Python compilation: passed.
- No live PayPal submission or production-money action was performed.
