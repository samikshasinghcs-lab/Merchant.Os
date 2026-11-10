# MerchantOS v0.5 — Checkpoint 5

## Root Cause & Predictive Intelligence (descriptive MVP)

### Delivered
- Deterministic complaint aggregation by category, product, and product batch.
- Complaint share, affected-order counts, affected-batch counts, and average ratings.
- Realized refund outflow grouped by currency, counting only records whose local status is explicitly `COMPLETED`.
- Unresolved complaint exposure: gross order value linked to medium/high-severity reviews without a `RESOLVED` resolution.
- Explicit methodology and limitations in the API response.

### API
- `GET /api/root-cause`

### Important interpretation boundaries
- Batch/product concentration is correlation, not proof of causation.
- Gross order value at risk is not a predicted loss, refund liability, or verified savings.
- Pending, proposed, rejected, and simulated refunds are excluded from realized refund outflow.
- Data quality depends on merchant-entered order, batch, category, and resolution records.
- No machine-learning prediction or autonomous intervention is claimed in this checkpoint.

### Verification
- `pytest -q`: 15 passed.
- Python compilation: passed.
- API smoke test: passed (HTTP 200, expected seed counts and response sections).
