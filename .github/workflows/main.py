"""Render Workflow: MerchantOS resolution pipeline.
Local:  render ea tasks dev -- render-workflows workflows.main:app
Deploy: Render Dashboard -> New -> Workflow -> start command: render-workflows workflows.main:app
"""
from render_sdk import Retry, Workflows
from app.intelligence import (detect_anomalies, build_graph,
                              simulate_policy, audit_chain)

app = Workflows(default_retry=Retry(max_retries=2, wait_duration_ms=1000))


@app.task
def anomaly_task(transactions: list) -> list:
    return detect_anomalies(transactions)


@app.task
def graph_task(transactions: list) -> dict:
    return build_graph(transactions)


@app.task
def simulation_task(transactions: list, per_refund_cap: float, daily_cap: float) -> dict:
    return simulate_policy(transactions, per_refund_cap, daily_cap)


@app.task
def audit_task(events: list) -> dict:
    return audit_chain(events)


@app.task
async def run_resolution_pipeline(transactions: list, events: list,
                                  per_refund_cap: float = 100.0,
                                  daily_cap: float = 500.0) -> dict:
    anomalies = await anomaly_task(transactions)
    graph = await graph_task(transactions)
    sim = await simulation_task(transactions, per_refund_cap, daily_cap)
    audit = await audit_task(events)
    return {"anomalies": anomalies, "graph": graph, "simulation": sim, "audit": audit}
