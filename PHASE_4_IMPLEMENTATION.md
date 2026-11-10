# MerchantOS — Phase 4: tenant-aware PayPal execution

## Scope
Phase 4 adds a narrow, approval-gated **PayPal Sandbox refund executor**. It is not a general-purpose payment execution agent and it cannot execute live-money refunds.

## Flow
1. An authenticated merchant creates a refund request; it starts `PENDING_RECONCILIATION`.
2. The server-side canonical reconciliation service checks the PayPal capture and deterministic policy.
3. A different OWNER/ADMIN approves the immutable request digest.
4. Only the recorded approver can invoke the execution endpoint.
5. MerchantOS reserves a unique tenant-scoped execution ledger row and stable PayPal `PayPal-Request-Id` before making the provider write.
6. The adapter uses that tenant's encrypted credentials and the Sandbox API host, re-reads the canonical capture, checks ID, currency, amount and refundable status, then submits the refund.
7. Success consumes the approval (`EXECUTED`). An ambiguous transport outcome is recorded as `UNKNOWN` and is never automatically retried.

## Controls
- `PAYPAL_EXECUTION_ENABLED=false` by default. Set it to `true` only after configuring tenant Sandbox credentials and validating the workflow.
- Live execution is explicitly rejected by this phase, even if the flag is enabled.
- No global PayPal credentials are used by the tenant adapter.
- The execution ledger has tenant RLS on PostgreSQL, unique approval reservation, and a stable provider idempotency key.
- A timeout after a provider POST is treated as ambiguous: inspect PayPal and reconcile manually; do not create another refund request.
- PayPal remains the final authority on the actual remaining refundable balance. MerchantOS does not infer cumulative refunded value from a capture response that may not contain it.
- No PAN/CVV is collected or stored.

## API
`POST /api/v1/operations/financial/refund-approvals/{approval_id}/execute`

Requires authentication, the original recorded approver, an approved request, tenant-specific Sandbox credentials, and `PAYPAL_EXECUTION_ENABLED=true`.

## Verification boundary
Unit tests cover adapter routing, tenant credential lookup, stable idempotency header, default-off execution, and live-mode rejection. A real end-to-end Sandbox refund still requires merchant credentials, a captured Sandbox payment, successful canonical reconciliation, an independent approver, and a deliberate manual test. PostgreSQL RLS and concurrency behavior require environment-backed integration tests. No live-money path is implemented.
