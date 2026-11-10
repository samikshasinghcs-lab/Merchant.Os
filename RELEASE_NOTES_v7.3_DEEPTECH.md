# MerchantOS v7.3 — DeepTech Intelligence & Assurance

## Release intent

This is a full-repository checkpoint that extends the existing MerchantOS codebase. It is not a replacement product or a second repository. The new DeepTech layer is intentionally isolated from payment execution.

## New capabilities

- Validated immutable transaction and simulation contracts.
- Canonical transaction payloads, SHA-256 fingerprints, and optional HMAC fingerprints.
- Deterministic transaction feature extraction.
- Robust median/MAD anomaly scoring with merchant/currency-local baselines and explainable signals.
- EWMA, CUSUM, quantiles, and drift measurement utilities.
- Tenant-scoped transaction relationship graph with connected components, weighted PageRank, degree centrality, and per-currency amount summaries.
- Seeded Monte Carlo merchant scenario simulation with explicit assumptions and limitations.
- Observational binary association screening that explicitly avoids causal claims.
- Hash-chained audit prototype with JSONL export/import and tamper verification.
- Model evaluation metrics, calibration tables, precision-recall thresholds, and chronological holdout splitting.
- Model-card metadata registry, privacy-aware pseudonymization helpers, and microbenchmark utility.
- Synthetic end-to-end demonstration and focused tests.

## Verification

Executed from the full release directory:

```bash
python -m pytest -q --disable-warnings --maxfail=1
```

Result: **177 passed, 1 skipped**.

Executed:

```bash
python -m app.deeptech.demo
```

Result: successful synthetic demonstration; audit chain verified; outlier signal produced; seeded simulation returned reproducible summary.

## Scope and limitations

- No trained fraud model is included.
- The anomaly detector is robust-statistics based, not machine-learning fraud classification.
- The graph is an in-memory prototype; scale and throughput have not been benchmarked.
- The digital twin is a scenario simulator with fixed order count/AOV and independent Bernoulli refund/dispute events. It is not a calibrated forecast or accounting system.
- Causal module reports observational associations only.
- Hash chain is a tamper-evident prototype, not WORM storage or a regulated ledger.
- No live PayPal execution is enabled by this release.
- Full PostgreSQL deployment, tenant RLS, load testing, external security review, and representative production-data validation remain separate release gates.

## Upgrade instructions

This ZIP contains the complete project tree. It is intended as a full checkpoint for inspection and testing. Preserve the existing GitHub repository history; review the file changes and merge/commit this checkpoint into the existing repository rather than creating a new repository or replacing Git history.
