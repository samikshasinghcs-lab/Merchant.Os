# MerchantOS v7.3.1 — Research Expansion

## Purpose

This checkpoint expands the existing MerchantOS repository in place. It adds
research-grade decision-support primitives while preserving the existing
financial execution and authorization boundaries.

## New capabilities in this expansion

### Conformal prediction

`research/conformal_prediction.py` implements split conformal regression using
absolute residuals and the conservative finite-sample order statistic. It also
supports explicitly grouped calibration. Undersized or unseen groups fail
closed instead of silently inheriting a global interval.

### Temporal validation

`research/temporal_validation.py` provides expanding walk-forward folds with a
time-based embargo, feature/label availability audits, and label maturity
selection. This is intended to reduce look-ahead leakage in financial event
models where settlement and dispute labels arrive after the original event.

### Explainability

`research/explainability.py` provides exact additive decompositions for linear
models and seeded permutation importance for callable predictors. Permutation
importance is a measure of model reliance, not a causal explanation. Correlated
features can split or mask importance.

### Reliability primitives

`research/resilience.py` adds a process-local circuit breaker, deterministic
bounded exponential-backoff decisions, and a bounded tenant-scoped in-memory
dead-letter quarantine. These utilities do not perform network calls, retries,
or financial writes. They are not distributed or durable infrastructure.

## Validation

The full repository test suite completed with **221 passed and 1 skipped**.
Python bytecode compilation completed successfully. The synthetic DeepTech demo
completed successfully and verified its sample hash chain.

## Research package size

The `app/deeptech/` and `tests/deeptech/` Python files contain 5,702 physical
lines, including 5,110 non-blank, non-comment lines. The original uploaded
GitHub snapshot contained neither directory, so these are new package lines
relative to that snapshot. Line count is reported for transparency and is not
a proxy for correctness, novelty, or production readiness.

## Safety and integration boundary

No module in the research package can directly authorize or execute a refund.
Any future integration must pass through MerchantOS's existing deterministic
policy, approval, tenant authorization, provider execution, reconciliation,
and audit controls. Before production use, the modules need threat modelling,
operational persistence, PostgreSQL integration tests, load tests, monitoring,
and independent review.
