# MerchantOS — Phase 3: Deterministic financial controls & maker-checker approvals

**Local implementation:** complete. **Live PayPal reconciliation and financial execution:** not enabled or verified.

## Product boundary

Phase 3 adds a tenant-scoped refund approval envelope. It does not turn an AI recommendation or a webhook into authority to move money. The operating rule remains:

**AI interprets → deterministic policy evaluates → canonical PayPal read verifies → a different authorized human approves → a separately guarded executor acts.**

## Implemented

- `app/financial_controls.py`: decimal-safe amount handling, currency/status checks, remaining capture balance, per-refund cap, daily cap, and explicit canonical-reconciliation requirement.
- `FinancialApprovalRequest`: tenant-bound approval record with unique request key, immutable financial payload digest, requester, approver, state, and timestamps.
- Authenticated routes under `/api/v1/operations/financial/refund-approvals` to create/list requests and record approval/rejection decisions.
- Maker-checker: requester cannot approve their own request; only OWNER/ADMIN can approve; only `PENDING_APPROVAL` may be decided; digest is recomputed before decision.
- Client-supplied `provider_status`, `capture_amount`, or `reconciliation_verified` are not accepted as evidence. New requests begin `PENDING_RECONCILIATION`.
- Internal service `record_canonical_capture_reconciliation(...)` is the only transition from reconciliation to `PENDING_APPROVAL` or `BLOCKED`; it expects the parsed result of a trusted PayPal capture GET and checks capture ID, amount, currency, status, refund limits.
- Alembic migration `0004_financial_approvals` applies PostgreSQL row-level security to the new tenant table.

## State machine

`PENDING_RECONCILIATION → PENDING_APPROVAL → APPROVED | REJECTED`

A failed canonical check becomes `BLOCKED`. There is no public route that can mark a request reconciled. The current code intentionally has no transition from `APPROVED` to PayPal execution: a tenant-aware PayPal adapter, idempotent execution record, and final preflight must be implemented and tested before money-moving operations are enabled.

## Verification

- Unit tests cover valid policy, missing reconciliation, currency mismatch, over-refund, per-refund and daily caps, invalid provider status, digest binding, maker-checker separation, role enforcement, and one-time decision state.
- API/DB integration and PostgreSQL RLS behavior require environment-backed integration tests; they are not represented as passed by the unit suite.
- PayPal Sandbox canonical capture reads and end-to-end refund execution remain unverified.
