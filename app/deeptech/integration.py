"""Merchant-scoped orchestration for the DeepTech transaction primitives.

This module is an integration boundary, not an API or persistence layer. Callers
must authenticate the actor and authorize access to ``merchant_id`` before
calling it. It accepts only explicitly supplied historical transactions and
never executes or authorizes financial actions.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import asdict
from typing import Any, Iterable, Mapping

from .anomaly import AnomalyConfig, RobustAnomalyDetector
from .fingerprints import transaction_fingerprint
from .graph import TransactionGraph
from .models import Transaction


class MerchantScopeError(ValueError):
    """Raised when an analysis batch crosses the requested merchant boundary."""


def _transaction(value: Transaction | Mapping[str, Any]) -> Transaction:
    return value if isinstance(value, Transaction) else Transaction.from_mapping(value)


def analyze_merchant_transactions(
    merchant_id: str,
    historical: Iterable[Transaction | Mapping[str, Any]],
    observed: Iterable[Transaction | Mapping[str, Any]],
    *,
    fingerprint_key: bytes | None = None,
    anomaly_config: AnomalyConfig | None = None,
) -> dict[str, Any]:
    """Analyze one merchant's observations against an explicitly separate history.

    The caller is responsible for obtaining both collections from an authorized,
    tenant-scoped source. Cross-merchant rows are rejected rather than filtered.
    Observed transactions are never included in the detector's fitted baseline.
    Customer identifiers are excluded from externally returned fingerprints.
    """
    merchant_id = str(merchant_id).strip()
    if not merchant_id:
        raise ValueError("merchant_id is required")

    history = [_transaction(item) for item in historical]
    current = [_transaction(item) for item in observed]
    if not current:
        raise ValueError("at least one observed transaction is required")

    all_rows = history + current
    foreign = sorted({row.merchant_id for row in all_rows if row.merchant_id != merchant_id})
    if foreign:
        raise MerchantScopeError(
            "analysis batch contains transactions outside the requested merchant scope"
        )

    # Require unique identifiers across both sets to prevent accidental replay or
    # baseline/observation overlap from distorting graph and anomaly calculations.
    identifiers = [row.transaction_id for row in all_rows]
    if len(identifiers) != len(set(identifiers)):
        raise ValueError("transaction identifiers must be unique across history and observations")

    detector = RobustAnomalyDetector(anomaly_config)
    detector.fit(history)
    findings = detector.score(current) if history else []

    graph = TransactionGraph()
    for row in all_rows:
        graph.add_transaction(row)
    graph_edges = graph.export_edges()

    return {
        "merchant_id": merchant_id,
        "methodology": {
            "anomaly_detector": "merchant-local robust statistics",
            "baseline_transaction_count": len(history),
            "observed_transaction_count": len(current),
            "observations_excluded_from_baseline": True,
            "predictive_model": False,
            "causal_claims": False,
            "financial_execution": False,
            "limitations": [
                "Anomaly scores are investigation signals, not fraud probabilities.",
                "A baseline smaller than the configured minimum cannot support amount z-scores.",
                "Graph edges represent exact identifier relationships, not identity proof.",
            ],
        },
        "transactions": [
            {
                "transaction_id": row.transaction_id,
                "fingerprint": transaction_fingerprint(
                    row, key=fingerprint_key, include_customer=False
                ),
                "anomaly": asdict(finding) if finding else None,
            }
            for row, finding in zip(current, findings or [None] * len(current))
        ],
        "graph": {
            "node_count": graph.node_count,
            "edge_count": graph.edge_count,
            "relationship_types": dict(Counter(
                edge["relation"] for edge in graph_edges
            )),
            "interpretation": "Exact-reference investigative relationships only; not proof of fraud or common ownership.",
        },
    }
