"""Run a deterministic, synthetic DeepTech walkthrough without merchant data."""
from __future__ import annotations
import json
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from .models import Transaction, Scenario
from .fingerprints import transaction_fingerprint
from .anomaly import RobustAnomalyDetector
from .graph import TransactionGraph
from .digital_twin import FinancialDigitalTwin
from .assurance import HashChain

def run_demo() -> dict[str, object]:
    now=datetime(2026,11,10,12,tzinfo=timezone.utc)
    history=[]
    for index in range(30):
        history.append(Transaction(f"demo_{index}","merchant_demo",Decimal("49.00") + Decimal(index % 4),"USD",now-timedelta(days=30-index),customer_id=f"customer_{index%9}",product_id=f"sku_{index%3}",channel="web",country="US"))
    detector=RobustAnomalyDetector().fit(history)
    probe=Transaction("demo_probe","merchant_demo",Decimal("499.00"),"USD",now,customer_id="customer_2",product_id="sku_1",channel="web",country="US")
    finding=detector.score_one(probe)
    graph=TransactionGraph.from_transactions(history+[probe])
    twin=FinancialDigitalTwin(seed=42).simulate(Scenario("baseline",1000,Decimal("49.00"),refund_rate=.04,dispute_rate=.01),iterations=2000)
    chain=HashChain(); chain.append("DEMO_ANALYSIS_CREATED","system:demo","merchant:merchant_demo",{"finding":finding.severity,"fingerprint":transaction_fingerprint(probe)})
    valid,verification=chain.verify()
    return {
        "notice":"SYNTHETIC DATA ONLY — not a production risk decision",
        "fingerprint":transaction_fingerprint(probe),
        "anomaly":{"score":finding.score,"severity":finding.severity,"signals":list(finding.signals)},
        "graph":{"nodes":graph.node_count,"edges":graph.edge_count,"components":len(graph.connected_components())},
        "simulation":{"mean_net_revenue":round(twin.mean_net_revenue,2),"p05":round(twin.p05_net_revenue,2),"p95":round(twin.p95_net_revenue,2),"probability_of_loss":twin.probability_of_loss,"seed":twin.seed},
        "audit":{"valid":valid,**verification},
    }

if __name__ == "__main__":
    print(json.dumps(run_demo(),indent=2,sort_keys=True))
