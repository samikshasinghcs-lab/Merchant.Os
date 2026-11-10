# MerchantOS DeepTech Architecture (experimental v0.1)

## Engineering thesis

MerchantOS is evolving from merchant workflow automation toward a computational financial intelligence and assurance platform. The DeepTech package is an isolated, deterministic analytical layer. It is deliberately not wired to payment execution and cannot approve, initiate, or retry a payment.

## Subsystems

| Module | Responsibility | Output | Explicit boundary |
|---|---|---|---|
| `models.py` | Validated transaction/scenario contracts | Typed immutable records | Does not persist records |
| `fingerprints.py` | Canonicalization and SHA-256/HMAC fingerprints | Stable digest and deterministic features | Fingerprint is not a digital signature |
| `statistics.py` | Robust descriptive statistics, EWMA, CUSUM | Statistics and change flags | No causal or fraud claim |
| `anomaly.py` | Merchant/currency-local robust baseline | Explainable anomaly findings | Rules/statistics, not trained fraud AI |
| `graph.py` | Exact-identifier transaction graph | Components, degree, PageRank | Co-occurrence is not common ownership or fraud proof |
| `digital_twin.py` | Reproducible Monte Carlo scenario analysis | Distribution summaries and assumptions | Scenario model, not calibrated forecast/accounting |
| `causal.py` | 2x2 observational association screening | Candidate hypotheses and caveats | Does not establish causality |
| `assurance.py` | Append-only in-process hash chain | Tamper-evident audit sequence | Not WORM storage; full-chain rewrite requires external anchoring to detect |
| `evaluation.py` | Classification/probability evaluation | Precision, recall, F1, Brier, calibration | Requires valid labelled holdout data |
| `drift.py` | Population stability index | Feature drift indicator | Drift is not model quality |
| `registry.py` | Model-card metadata | Reproducibility/provenance record | Does not store or execute model artifacts |
| `privacy.py` | Pseudonymization and field removal | Safer analytical export | Not legal anonymization or a compliance certification |
| `benchmark.py` | Local microbenchmark helper | Runtime samples | Hardware-dependent, not a published benchmark |

## Data flow

```text
Authorized source data
        |
        v
Validated transaction contract
        |
        +--> Canonical fingerprint / feature extraction
        |
        +--> Merchant-local robust anomaly analysis
        |
        +--> Exact identifier relationship graph
        |
        +--> Observational association screening
        |
        +--> Scenario simulation (explicit assumptions)
        |
        v
Evaluation + drift monitoring + model cards
        |
        v
Hash-chained analytical audit evidence
```

The package does not load merchant records itself. The host application must enforce authentication, tenant authorization, data minimization, consent/legal basis, retention, and secure storage before passing records into these functions.

## Reproducibility

- Use immutable `Transaction` and `Scenario` values.
- Use fixed seeds for simulations and record the seed in each result.
- Keep model evaluation strictly temporal where event timestamps exist.
- Record dataset references and evaluation references in model cards.
- Keep synthetic demonstration data separate from production datasets.
- Never publish benchmark numbers without the hardware, runtime, dataset size, warm-up, and repetition protocol.

## Security and financial safety

DeepTech outputs are advisory. They must not directly mutate balances, approve refunds, bypass maker-checker controls, or invoke PayPal. A future API integration must pass findings through existing tenant-scoped authorization and deterministic policy controls. Treat metadata, product labels, free text, and graph identifiers as untrusted input.

## Known limitations / next validation gates

1. The in-memory graph is designed for prototype-scale analysis; large graph storage needs a separately benchmarked graph backend.
2. Anomaly baselines require sufficient historical data, seasonality controls, and temporal backtesting before operational use.
3. Monte Carlo currently uses fixed order count/AOV and independent Bernoulli refund/dispute events. It omits taxes, shipping, settlement timing, chargeback fees, recoveries, correlation, and working-capital constraints.
4. Association screening is exploratory; confounding, sparse-cell effects, multiple testing, and selection bias remain.
5. The hash chain is a local integrity primitive, not a regulated immutable ledger. Production use requires durable transactional storage, concurrency control, external signed checkpoints, key rotation, and access controls.
6. No model is trained by this release. The detector is deterministic and explainable.
7. No performance or accuracy claim is made until representative, permissioned, labelled datasets are available.
