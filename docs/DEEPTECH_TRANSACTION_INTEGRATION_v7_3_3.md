# MerchantOS v7.3.3 — Transaction Intelligence Integration

## What changed

`app.deeptech.integration.analyze_merchant_transactions` is the orchestration
boundary connecting the existing transaction domain model, canonical
fingerprinting, merchant-local robust anomaly detection, and relationship graph.
It accepts an explicitly supplied historical dataset and a separate observed
batch. Observations are not included in the fitted anomaly baseline.

## Contract

- The caller MUST authenticate the actor and authorize access to the requested
  merchant before invoking this function.
- All rows must belong to the requested merchant. Cross-merchant input is
  rejected with `MerchantScopeError`.
- Transaction identifiers must be unique across history and observed rows.
- Customer identifiers are excluded from returned transaction fingerprints.
- The graph reports exact-reference co-occurrence only. It does not establish
  identity, fraud, common ownership, or causation.
- The anomaly detector is a transparent statistical investigation aid, not a
  trained fraud model and not a calibrated probability.
- The function is read-only: it does not persist records, authorize refunds,
  call a payment provider, or execute financial actions.

## Why this is an internal service, not yet a public endpoint

The legacy review/order store and the typed DeepTech transaction model do not
currently share a fully verified tenant-scoped persistence adapter. Exposing
this analysis through an unauthenticated HTTP route would create a data
isolation risk. A public endpoint is deliberately deferred until a verified
identity dependency and tenant-scoped repository adapter are wired end to end.

## Tests

`tests/deeptech/test_integration.py` covers merchant-boundary rejection,
identifier uniqueness, historical-baseline separation, customer-identifier
omission from returned fingerprints, and empty/invalid input handling.

## Verification scope

The local Python suite and compilation were run on this development snapshot.
This does not certify live GitHub state, PostgreSQL row-level security, provider
integration, production readiness, or model predictive performance.
