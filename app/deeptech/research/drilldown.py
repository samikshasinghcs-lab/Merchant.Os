"""Evidence drill-down and explanation assembly with provenance identifiers."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Mapping, Sequence

@dataclass(frozen=True, slots=True)
class Evidence:
    evidence_id: str
    source_type: str
    source_reference: str
    observed_at: str
    attributes: Mapping[str,Any]
    reliability: float
    def __post_init__(self):
        if not self.evidence_id or not self.source_type or not self.source_reference: raise ValueError("evidence identity required")
        if not 0<=self.reliability<=1: raise ValueError("reliability must be in [0,1]")

@dataclass(frozen=True, slots=True)
class Explanation:
    finding_code: str
    summary: str
    evidence_ids: tuple[str,...]
    confidence: float
    limitations: tuple[str,...]

class ExplanationBuilder:
    def build(self,finding_code: str,summary: str,evidence: Sequence[Evidence],limitations: Sequence[str]=()) -> Explanation:
        if not finding_code or not summary: raise ValueError("finding code and summary required")
        if len({e.evidence_id for e in evidence})!=len(evidence): raise ValueError("duplicate evidence identifiers")
        confidence=sum(e.reliability for e in evidence)/len(evidence) if evidence else 0.0
        return Explanation(finding_code,summary,tuple(e.evidence_id for e in evidence),confidence,tuple(limitations))
    def validate_references(self,explanation: Explanation,evidence: Sequence[Evidence]) -> bool:
        available={item.evidence_id for item in evidence}
        return set(explanation.evidence_ids)<=available
