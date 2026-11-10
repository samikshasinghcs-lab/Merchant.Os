# MerchantOS Checkpoint 2 — PayPal Sandbox checkout

## Implemented
- Backend-only OAuth 2.0 client-credentials flow for PayPal REST API.
- PayPal Sandbox checkout order creation (`CAPTURE` intent) with request idempotency.
- Approval URL returned to the merchant so the buyer can approve on PayPal.
- Capture endpoint with a stable idempotency key.
- Completed capture ID, amount, and currency are validated and persisted to the local order.
- Repeated capture requests return the existing capture without issuing another capture call.
- Checkout endpoints refuse to run in demo mode and refuse non-Sandbox mode.
- Network/API errors are normalized into safe API errors and audit events.

## Verification
Automated integration tests mock PayPal's HTTP-level adapter responses and verify order creation, approval URL handoff, capture persistence, amount/currency validation path, and repeat-capture protection. These tests do **not** prove a live PayPal Sandbox transaction. Real verification requires a PayPal Developer Sandbox REST app, a Sandbox buyer account, and manual approval.

## How to run a real Sandbox round-trip
Follow the PayPal Sandbox section in the README. Never put credentials in frontend code, screenshots, source control, or chat. Use only Sandbox buyer accounts and small test amounts.

## Not yet production-ready
- No webhook endpoint/signature verification or asynchronous capture/refund reconciliation.
- No user authentication, merchant tenancy, encrypted credential vault, or rate limiting.
- SQLite demo storage is not a production financial ledger; concurrent payment/refund operations need transactional reservation and reconciliation.
- PayPal return/cancel URLs are local development placeholders; configure public HTTPS URLs for a deployed demo.
- Refund approvals remain human-triggered. Seeded transactions are illustrative and are not PayPal transactions.
