# MerchantOS — Checkpoint 3: Evidence Intelligence

## Delivered
- Merchant evidence registry with order linkage and controlled evidence-type taxonomy.
- Evidence references are explicitly marked `merchant_supplied_unverified`; this MVP stores descriptions/references, not files, and does not authenticate source material.
- Deterministic dispute evidence assessment: required evidence categories, present categories, missing categories, and a transparent coverage percentage.
- Reason-specific evidence prompts for delivery-not-received, not-as-described, damaged/defective, duplicate-charge, and credit-not-processed cases; unknown reasons use a conservative baseline.
- Evidence registration is written to the existing audit log.
- API endpoints:
  - `POST /api/evidence`
  - `GET /api/evidence?order_id=<merchant_order_id>`
  - `GET /api/disputes/{dispute_id}/assessment`

## Example
```json
POST /api/evidence
{
  "order_id": "<existing merchant order id>",
  "evidence_type": "tracking",
  "description": "Carrier tracking page shows delivery scan on 2026-11-08",
  "reference": "https://carrier.example/track/123"
}
```

## Important boundaries
- The coverage percentage is category coverage only. It is not a probability of winning a dispute, a legal sufficiency score, or proof of authenticity.
- No evidence is submitted to PayPal automatically.
- This checkpoint does not fetch or verify carrier records, inspect uploaded files, or verify PayPal dispute records.
- Human review remains mandatory.

## Verification
Run `pytest -q` from this directory. The evidence tests use a temporary SQLite database and do not call PayPal.
