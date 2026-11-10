"""Constraint checks for scenario outputs and financial decision proposals."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Mapping, Sequence

@dataclass(frozen=True, slots=True)
class Constraint:
    name: str
    field: str
    operator: str
    limit: float
    severity: str="high"
    def __post_init__(self):
        if self.operator not in {"min","max","equal","non_negative","finite"}: raise ValueError("unsupported constraint")
        if self.severity not in {"low","medium","high","critical"}: raise ValueError("invalid severity")

@dataclass(frozen=True, slots=True)
class ConstraintViolation:
    name: str
    field: str
    actual: object
    limit: float
    severity: str
    explanation: str

class ConstraintEngine:
    def evaluate(self,values: Mapping[str,object],constraints: Sequence[Constraint]) -> tuple[ConstraintViolation,...]:
        violations=[]
        for rule in constraints:
            if rule.field not in values:
                violations.append(ConstraintViolation(rule.name,rule.field,None,rule.limit,rule.severity,"required field is missing")); continue
            actual=values[rule.field]
            if rule.operator=="finite": passed=__import__("math").isfinite(float(actual))
            elif rule.operator=="non_negative": passed=float(actual)>=0
            elif rule.operator=="min": passed=float(actual)>=rule.limit
            elif rule.operator=="max": passed=float(actual)<=rule.limit
            else: passed=float(actual)==rule.limit
            if not passed: violations.append(ConstraintViolation(rule.name,rule.field,actual,rule.limit,rule.severity,f"constraint {rule.operator} {rule.limit} failed"))
        return tuple(violations)
    def assert_valid(self,values: Mapping[str,object],constraints: Sequence[Constraint]) -> None:
        failures=self.evaluate(values,constraints)
        if failures: raise ValueError("; ".join(f"{item.name}: {item.explanation}" for item in failures))
