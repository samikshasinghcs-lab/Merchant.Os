# Refund reconciliation — v6.2

## Endpoint

`POST /api/v1/operations/financial/refund-approvals/{approval_id}/reconcile`

Requires an authenticated `OWNER`, `ADMIN`, or `OPERATOR`. The endpoint accepts no body and ignores no client-supplied provider facts because none are accepted. It loads the approval request in the authenticated tenant, uses that tenant's configured PayPal Sandbox credentials, and fetches `GET /v2/payments/captures/{capture_id}`.

## State transitions

- `PENDING_RECONCILIATION` + canonical `COMPLETED` capture + policy allowed → `PENDING_APPROVAL`.
- Partial, fully refunded, pending, denied, or unknown capture status → `BLOCKED`.
- Provider read failure → request remains `PENDING_RECONCILIATION`; API returns a provider-read error.
- Capture ID mismatch or invalid canonical response → no approval is granted.

## Financial guardrails and known limitation

PayPal's capture GET response does not supply a reliable cumulative refund amount. Therefore the implementation does not guess a remaining balance: it only auto-reconciles a capture whose canonical status is `COMPLETED`; any other status is blocked.

The daily refund cap currently counts MerchantOS execution reservations and outcomes for the current UTC day and currency, including `RESERVED`, `SUCCEEDED`, and `UNKNOWN` outcomes. It does not include refunds initiated directly in the PayPal dashboard or by another system. This is an explicit limitation, not a claim of complete merchant-wide reconciliation. Do not treat this release as production-ready for merchants who can issue refunds outside MerchantOS. An authoritative merchant-wide ledger is required before widening deployment.

## Tests

`tests/test_refund_reconciliation_route.py` verifies successful canonical capture reconciliation, fail-closed handling of partial refunds, and preservation of pending state when PayPal reads fail. These tests use a fake adapter; they do not prove live Sandbox connectivity.
