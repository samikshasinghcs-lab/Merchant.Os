"""Composable, explainable merchant risk scoring; never an authorization engine."""
from __future__ import annotations
from dataclasses import dataclass
from math import isfinite
from typing import Mapping, Sequence

@dataclass(frozen=True, slots=True)
class RiskSignal:
    name: str
    value: float
    weight: float
    direction: str = "higher_is_riskier"
    rationale: str = ""
    def __post_init__(self) -> None:
        if not self.name or not isfinite(float(self.value)) or not isfinite(float(self.weight)): raise ValueError("invalid risk signal")
        if self.weight<0: raise ValueError("weight cannot be negative")
        if self.direction not in {"higher_is_riskier","lower_is_riskier"}: raise ValueError("invalid direction")

@dataclass(frozen=True, slots=True)
class RiskAssessment:
    score: float
    band: str
    contributions: Mapping[str,float]
    missing_signals: tuple[str,...]
    policy_version: str
    disclaimer: str = "decision support only; not a credit, fraud, or payment authorization decision"

class RiskModel:
    def __init__(self,weights: Mapping[str,float],version: str="1",thresholds: tuple[float,float,float]=(.25,.5,.75)) -> None:
        if not weights or any(float(v)<0 for v in weights.values()): raise ValueError("non-negative weights required")
        if sum(weights.values())<=0: raise ValueError("at least one positive weight required")
        if tuple(sorted(thresholds))!=thresholds or any(not 0<=x<=1 for x in thresholds): raise ValueError("thresholds must be sorted in [0,1]")
        self.weights={k:float(v) for k,v in weights.items()}; self.version=version; self.thresholds=thresholds
    def assess(self,values: Mapping[str,float]) -> RiskAssessment:
        contributions={}; missing=[]; denominator=0.0
        for name,weight in self.weights.items():
            if name not in values: missing.append(name); continue
            value=float(values[name])
            if not isfinite(value) or not 0<=value<=1: raise ValueError(f"{name} must be a probability-like value")
            contributions[name]=value*weight; denominator+=weight
        if denominator==0: raise ValueError("no configured risk signals supplied")
        score=sum(contributions.values())/denominator
        low,medium,high=self.thresholds
        band="low" if score<low else "guarded" if score<medium else "elevated" if score<high else "critical"
        return RiskAssessment(score,band,contributions,tuple(missing),self.version)
    def explain(self,assessment: RiskAssessment) -> tuple[str,...]:
        total=sum(assessment.contributions.values()) or 1.0
        return tuple(f"{name}: {value/total:.1%} of observed weighted risk contribution" for name,value in sorted(assessment.contributions.items(),key=lambda x:(-x[1],x[0])))

class RiskPolicy:
    """Maps assessment bands to review queues; deliberately cannot execute actions."""
    QUEUES={"low":"routine_monitoring","guarded":"standard_review","elevated":"priority_review","critical":"urgent_human_review"}
    def route(self,assessment: RiskAssessment) -> dict:
        return {"queue":self.QUEUES[assessment.band],"requires_human_review":assessment.band in {"elevated","critical"},"risk_score":assessment.score,"policy_version":assessment.policy_version}
