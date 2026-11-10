"""Dispute triage prioritization based on deadline, value, and evidence readiness."""
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Mapping

@dataclass(frozen=True, slots=True)
class DisputeCase:
    case_id: str
    tenant_id: str
    amount: float
    deadline: datetime
    evidence_completeness: float
    customer_history_risk: float
    status: str="open"
    def __post_init__(self):
        if not self.case_id or not self.tenant_id or self.deadline.tzinfo is None: raise ValueError("case identity and aware deadline required")
        if self.amount<0 or not 0<=self.evidence_completeness<=1 or not 0<=self.customer_history_risk<=1: raise ValueError("invalid case metrics")

class DisputePrioritizer:
    def score(self,case: DisputeCase,now: datetime|None=None) -> dict:
        stamp=now or datetime.now(timezone.utc)
        if stamp.tzinfo is None: raise ValueError("now must be timezone-aware")
        hours=(case.deadline-stamp).total_seconds()/3600
        urgency=1.0 if hours<=0 else max(0.0,min(1.0,1-hours/(24*14)))
        value=min(1.0,case.amount/1000)
        evidence_gap=1-case.evidence_completeness
        score=.4*urgency+.25*value+.2*evidence_gap+.15*case.customer_history_risk
        band="critical" if score>=.8 else "high" if score>=.6 else "medium" if score>=.35 else "low"
        return {"case_id":case.case_id,"score":score,"band":band,"hours_to_deadline":hours,"drivers":{"urgency":urgency,"value":value,"evidence_gap":evidence_gap,"customer_history_risk":case.customer_history_risk},"recommendation":"human review required; score does not determine dispute outcome"}
    def rank(self,cases,now=None):
        return tuple(sorted((self.score(case,now) for case in cases),key=lambda row:(-row["score"],row["hours_to_deadline"],row["case_id"])))
