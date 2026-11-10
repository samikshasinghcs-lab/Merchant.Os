"""Declarative rule evaluation for deterministic policy recommendations."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Mapping, Sequence

@dataclass(frozen=True, slots=True)
class Rule:
    rule_id: str
    field: str
    operator: str
    threshold: Any
    outcome: str
    priority: int=100
    rationale: str=""
    def __post_init__(self):
        if not all((self.rule_id,self.field,self.outcome)): raise ValueError("rule identity required")
        if self.operator not in {"eq","ne","gt","gte","lt","lte","in","contains","exists"}: raise ValueError("unsupported operator")

def evaluate_rule(rule: Rule,context: Mapping[str,Any]) -> bool:
    exists=rule.field in context; value=context.get(rule.field)
    if rule.operator=="exists": return exists
    if not exists: return False
    if rule.operator=="eq": return value==rule.threshold
    if rule.operator=="ne": return value!=rule.threshold
    if rule.operator=="gt": return value>rule.threshold
    if rule.operator=="gte": return value>=rule.threshold
    if rule.operator=="lt": return value<rule.threshold
    if rule.operator=="lte": return value<=rule.threshold
    if rule.operator=="in": return value in rule.threshold
    if rule.operator=="contains": return rule.threshold in value
    return False

class RuleEngine:
    def __init__(self,rules: Sequence[Rule]):
        ids=[rule.rule_id for rule in rules]
        if len(ids)!=len(set(ids)): raise ValueError("rule ids must be unique")
        self.rules=tuple(sorted(rules,key=lambda r:(r.priority,r.rule_id)))
    def evaluate(self,context: Mapping[str,Any]) -> tuple[Rule,...]:
        return tuple(rule for rule in self.rules if evaluate_rule(rule,context))
    def recommend(self,context: Mapping[str,Any],default: str="review") -> dict:
        matches=self.evaluate(context)
        selected=matches[0] if matches else None
        return {"outcome":selected.outcome if selected else default,"matched_rule":selected.rule_id if selected else None,"matched_rules":[r.rule_id for r in matches],"rationale":selected.rationale if selected else "no rule matched"}
