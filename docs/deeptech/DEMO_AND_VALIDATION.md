# DeepTech demo and validation guide

## Run synthetic demo

```bash
python -m app.deeptech.demo
```

The output is generated entirely from synthetic transactions and a fixed random seed. It demonstrates stable transaction fingerprints, a high-value anomaly signal, exact-identifier graph construction, a Monte Carlo scenario, and audit-chain verification.

## Run tests

```bash
python -m pytest -q
```

## Suggested technical demo sequence

1. Show a normal synthetic merchant transaction baseline.
2. Introduce one synthetic outlier and inspect the explainable anomaly signals.
3. Show that graph links arise only from exact identifiers in the same transaction.
4. Run the same financial scenario twice with the same seed and show reproducible percentiles.
5. Alter an exported audit event and show that chain verification rejects it.
6. Show evaluation metrics and temporal split utilities; explain that they require labelled, permissioned data.

## Claims allowed in a presentation

- “Deterministic transaction fingerprinting with optional keyed HMAC.”
- “Explainable robust-statistics anomaly scoring.”
- “Exact-identifier transaction relationship graph.”
- “Seeded Monte Carlo scenario simulation with disclosed assumptions.”
- “Tamper-evident hash-chain prototype.”
- “Model evaluation and feature drift measurement utilities.”

## Claims not supported by this release

- “AI detects fraud with 99% accuracy.”
- “Causal root-cause discovery is proven.”
- “Blockchain-grade immutable audit ledger.”
- “Production digital twin.”
- “Real-time graph neural network.”
- “NVIDIA/ASML-grade performance.”

Those claims would require trained and validated models, production-scale data infrastructure, security review, external anchoring, load tests, and independently reproducible evidence.
