"""Composable matching rules for financial reconciliation exceptions."""
from __future__ import annotations
from dataclasses import dataclass
from decimal import Decimal
from typing import Mapping, Sequence

@dataclass(frozen=True, slots=True)
class MatchCandidate:
    internal_id: str
    provider_id: str
    reference_match: bool
    amount_delta: Decimal
    timestamp_delta_seconds: float
    currency_match: bool
    def score(self,amount_tolerance: Decimal,time_tolerance: float) -> float:
        if not self.currency_match: return 0.0
        score=0.0
        if self.reference_match: score+=.65
        if abs(self.amount_delta)<=amount_tolerance: score+=.25
        if self.timestamp_delta_seconds<=time_tolerance: score+=.10
        return score

class CandidateMatcher:
    def rank(self,candidates: Sequence[MatchCandidate],amount_tolerance: Decimal=Decimal("0.01"),time_tolerance: float=86400) -> tuple[tuple[MatchCandidate,float],...]:
        if amount_tolerance<0 or time_tolerance<0: raise ValueError("tolerances must be non-negative")
        ranked=[(item,item.score(amount_tolerance,time_tolerance)) for item in candidates]
        return tuple(sorted(ranked,key=lambda pair:(-pair[1],pair[0].internal_id,pair[0].provider_id)))
    def unambiguous(self,candidates: Sequence[MatchCandidate],minimum_score: float=.9,margin: float=.1):
        ranked=self.rank(candidates)
        if not ranked or ranked[0][1]<minimum_score: return None
        if len(ranked)>1 and ranked[0][1]-ranked[1][1]<margin: return None
        return ranked[0][0]

def classify_delta(internal: Decimal,provider: Decimal,tolerance: Decimal=Decimal("0.01")) -> str:
    a=Decimal(str(internal)); b=Decimal(str(provider)); tol=Decimal(str(tolerance))
    if tol<0: raise ValueError("tolerance must be non-negative")
    if a==b: return "EXACT_MATCH"
    if abs(a-b)<=tol: return "ROUNDING_VARIANCE"
    return "MATERIAL_AMOUNT_MISMATCH"
