"""Pure deterministic payload builder used by the deployed Render Workflow task."""
from __future__ import annotations
from typing import Any


def build_resolution_pipeline(transactions: list[dict], events: list[dict],
                              per_refund_cap: float = 100.0,
                              daily_cap: float = 500.0, run_id: str | None = None) -> dict[str, Any]:
    # Reuse the same validated intelligence functions exposed by the authenticated API.
    from .intelligence import (RunIn, validate_input, detect_anomalies, build_graph,
                               simulate_policy, audit_chain)
    request = RunIn(transactions=transactions, events=events,
                    per_refund_cap=per_refund_cap, daily_cap=daily_cap)
    validate_input(request)
    return {
        "workflow": "run_resolution_pipeline",
        "run_id": run_id,
        "anomalies": detect_anomalies(transactions),
        "graph": build_graph(transactions),
        "simulation": simulate_policy(transactions, per_refund_cap, daily_cap),
        "audit": audit_chain(events),
        "financial_action": "NONE",
        "disclosure": "Deterministic analysis only. This workflow does not approve refunds, move money, or mutate inventory.",
    }
