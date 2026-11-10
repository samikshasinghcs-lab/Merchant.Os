"""Tenant-scoped orchestration facade for read-only analytical components."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Iterable, Mapping, Any
from .types import Observation, Finding
from .features import TransactionFeatureExtractor
from .anomaly import RobustBaseline
from .graph import GraphBuilder
from .risk import RiskModel, RiskPolicy

@dataclass(frozen=True, slots=True)
class PipelineReport:
    tenant_id: str
    observation_count: int
    findings: tuple[Finding,...]
    graph_summary: Mapping[str,Any]
    disclaimer: str="analytics only; does not authorize or execute financial actions"

class IntelligencePipeline:
    def __init__(self,tenant_id: str) -> None:
        if not tenant_id: raise ValueError("tenant_id required")
        self.tenant_id=tenant_id; self.extractor=TransactionFeatureExtractor(); self.baseline=RobustBaseline(5); self.risk_model=RiskModel({"amount_deviation":.4,"velocity_deviation":.35,"relationship_centrality":.25}); self.policy=RiskPolicy()
    def fit_baseline(self,observations: Iterable[Observation]) -> None:
        rows=list(observations)
        if any(item.merchant_id!=self.tenant_id for item in rows): raise PermissionError("cross-tenant baseline rejected")
        vectors=self.extractor.batch(rows); self.baseline.fit([vector.values for vector in vectors])
    def analyze(self,observations: Iterable[Observation]) -> PipelineReport:
        rows=list(observations)
        if any(item.merchant_id!=self.tenant_id for item in rows): raise PermissionError("cross-tenant observations rejected")
        vectors=self.extractor.batch(rows); findings=[]
        for vector in vectors:
            findings.extend(self.baseline.score(vector.values))
        graph=GraphBuilder(self.tenant_id)
        by_customer={}
        for item in rows:
            customer=item.attributes.get("customer_id")
            if customer:
                graph.relate("customer",str(customer),"transaction",item.observation_id,"CUSTOMER_TRANSACTION",1.0,item.observation_id)
                by_customer.setdefault(str(customer),[]).append(item)
        summary={"nodes":len(graph.graph.nodes),"edges":len(graph.graph.edges),"components":len(graph.graph.connected_components()),"customer_groups":len(by_customer)}
        return PipelineReport(self.tenant_id,len(rows),tuple(findings),summary)
