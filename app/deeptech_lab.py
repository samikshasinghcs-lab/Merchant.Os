"""Read-only DeepTech showcase computed from the merchant's own orders and audit log.

Four independent, explainable engines: anomaly scoring, exact-identifier graph,
seeded Monte Carlo scenario, and a tamper-evident hash chain. Advisory only;
nothing here can approve, block or execute a payment.
"""
import json
from dataclasses import replace
from decimal import Decimal
from .db import db
from .deeptech.assurance import HashChain
from .deeptech.digital_twin import FinancialDigitalTwin
from .deeptech.graph import TransactionGraph
from .deeptech.models import Scenario, Transaction
from .refund_risk import MERCHANT_ID, _tx, risk_for_order


def _audit_chain(rows):
    chain = HashChain()
    for r in rows:
        try:
            detail = json.loads(r["detail"]) if r["detail"] else {}
        except Exception:
            detail = {"detail": str(r["detail"])[:200]}
        if not isinstance(detail, dict):
            detail = {"detail": str(detail)[:200]}
        chain.append(str(r["event"] or "EVENT"), str(r["actor"] or "system"),
                     str(r["entity"] or "none"), detail)
    ok, info = chain.verify()
    tamper = {"tested": False}
    evs = list(chain.events)
    if evs:
        bad = replace(evs[len(evs) // 2], payload={"tampered": True})
        try:
            HashChain(evs[: len(evs) // 2] + [bad] + evs[len(evs) // 2 + 1:])
            tamper = {"tested": True, "detected": False}
        except ValueError:
            tamper = {"tested": True, "detected": True}
    return {"events": len(evs), "valid": ok, "head_hash": info.get("head_hash"),
            "tamper_test": tamper}


def lab_report():
    with db() as c:
        orders = c.execute("SELECT * FROM orders").fetchall()
        refunds = c.execute("SELECT COUNT(*) FROM refunds").fetchone()[0]
        audit = c.execute("SELECT * FROM audit ORDER BY id ASC LIMIT 300").fetchall()
    out = {"notice": "Computed from this workspace's records. Advisory signals, not fraud verdicts.",
           "orders": len(orders)}
    # 1. Anomaly scoring (leave-one-out against the other orders)
    scored = []
    for r in orders:
        k = risk_for_order(r["id"])
        if k:
            scored.append({"order_id": r["id"], "amount": r["amount"],
                           "currency": r["currency"], **k})
    scored.sort(key=lambda x: -x["score"])
    out["anomaly"] = {"method": "merchant-local robust statistics", "top": scored[:3]}
    # 2. Exact-identifier transaction graph
    try:
        g = TransactionGraph.from_transactions([Transaction.from_mapping(_tx(r)) for r in orders])
        rel = {}
        for e in g.export_edges():
            rel[e["relation"]] = rel.get(e["relation"], 0) + 1
        out["graph"] = {"nodes": g.node_count, "edges": g.edge_count,
                        "components": len(g.connected_components()), "relationships": rel}
    except Exception:
        out["graph"] = None
    # 3. Seeded Monte Carlo scenario
    try:
        aov = sum(float(r["amount"]) for r in orders) / max(len(orders), 1)
        rate = min(max(refunds / max(len(orders), 1), 0.01), 0.5)
        s = Scenario("next 500 orders", 500, Decimal(str(round(aov, 2))),
                     refund_rate=rate, dispute_rate=0.01)
        t = FinancialDigitalTwin(seed=42).simulate(s, iterations=1000)
        out["simulation"] = {"scenario": s.name, "avg_order_value": round(aov, 2),
                             "refund_rate": round(rate, 3), "p05": round(t.p05_net_revenue, 2),
                             "median": round(t.median_net_revenue, 2),
                             "p95": round(t.p95_net_revenue, 2),
                             "probability_of_loss": t.probability_of_loss, "seed": t.seed,
                             "assumptions": "Illustrative scenario; rates and costs are assumptions."}
    except Exception:
        out["simulation"] = None
    # 4. Tamper-evident audit chain
    try:
        out["audit_chain"] = _audit_chain(audit)
    except Exception:
        out["audit_chain"] = None
    return out
