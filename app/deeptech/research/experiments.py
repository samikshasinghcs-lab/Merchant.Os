"""A/B experiment summaries with uncertainty and guardrail reporting."""
from __future__ import annotations
from dataclasses import dataclass
from math import sqrt
from typing import Iterable
from .statistics import mean, variance

@dataclass(frozen=True, slots=True)
class ExperimentResult:
    control_mean: float
    treatment_mean: float
    absolute_lift: float
    relative_lift: float|None
    standard_error: float
    confidence_interval: tuple[float,float]
    control_n: int
    treatment_n: int
    guardrail_passed: bool

class ExperimentAnalyzer:
    def compare_means(self,control: Iterable[float],treatment: Iterable[float],guardrail_minimum: float|None=None) -> ExperimentResult:
        a=list(map(float,control)); b=list(map(float,treatment))
        if len(a)<2 or len(b)<2: raise ValueError("at least two observations per arm")
        cm=mean(a); tm=mean(b); lift=tm-cm; se=sqrt(variance(a)/len(a)+variance(b)/len(b))
        passed=guardrail_minimum is None or tm>=guardrail_minimum
        return ExperimentResult(cm,tm,lift,None if cm==0 else lift/abs(cm),se,(lift-1.96*se,lift+1.96*se),len(a),len(b),passed)
    def conversion_rate(self,conversions: int,exposures: int) -> float:
        if exposures<=0 or conversions<0 or conversions>exposures: raise ValueError("invalid conversion counts")
        return conversions/exposures
    def compare_proportions(self,control_success: int,control_n: int,treatment_success: int,treatment_n: int) -> dict:
        if min(control_success,treatment_success)<0 or control_success>control_n or treatment_success>treatment_n or min(control_n,treatment_n)<=0: raise ValueError("invalid binomial counts")
        p0=control_success/control_n; p1=treatment_success/treatment_n; delta=p1-p0
        se=sqrt(p0*(1-p0)/control_n+p1*(1-p1)/treatment_n)
        return {"control_rate":p0,"treatment_rate":p1,"absolute_lift":delta,"relative_lift":None if p0==0 else delta/p0,"standard_error":se,"confidence_interval_95":(delta-1.96*se,delta+1.96*se)}
