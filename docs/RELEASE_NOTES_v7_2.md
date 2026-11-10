# MerchantOS v7.2 — Financial Execution State Integrity

## Scope

This checkpoint makes the provider execution lifecycle explicit and prevents a PayPal `PENDING` acknowledgement from being recorded as a confirmed financial success.

## Changes

- Added `app/execution_state_machine.py` with an explicit execution-state set and validated transitions.
- Separated `SUBMITTED` (provider accepted/processing acknowledgement) from `SUCCEEDED` (provider reports `COMPLETED`).
- Kept ambiguous provider outcomes in `UNKNOWN`; these are not automatically retried.
- Made `UNKNOWN` transition only to `RECONCILING`, preventing blind reset or resubmission.
- Added `RECONCILING` as an explicit operational state for future provider-status investigation.
- Updated conservative daily exposure accounting to include `SUBMITTED` and `RECONCILING` executions.
- Updated replay metadata so `SUBMITTED` and `RECONCILING` executions are not represented as safely retryable.
- Added focused tests for allowed and prohibited state transitions.

## Verification

Command:

```bash
python -m pytest -q --disable-warnings --maxfail=1
```

Result on the supplied repository snapshot after these changes: **123 passed, 1 skipped**.

## Important limitations

- This change does not implement a provider polling/reconciliation worker. `RECONCILING` is a defined state for that future capability, not a claim that reconciliation is already automated.
- Existing database rows previously stored as `SUCCEEDED` when PayPal returned `PENDING` are historical records and are not automatically rewritten. They require a separately designed, provider-backed reconciliation procedure; do not bulk-change them based only on local status.
- Live PayPal execution remains disabled by the existing sandbox-only guard.
- Passing the repository test suite does not establish production readiness or prove PostgreSQL row-level security in a live PostgreSQL deployment.
