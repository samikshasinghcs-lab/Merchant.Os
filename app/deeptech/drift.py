"""Feature drift monitors based on distribution summaries and PSI."""
from __future__ import annotations
from math import log
from typing import Mapping, Sequence
from .statistics import quantile

def population_stability_index(reference: Sequence[float], current: Sequence[float], bins: int = 10, epsilon: float = 1e-6) -> float:
    if len(reference) < bins or len(current) < bins or bins < 2:
        raise ValueError("both samples must contain at least `bins` values")
    if epsilon <= 0:
        raise ValueError("epsilon must be positive")
    # Quantile boundaries reduce sensitivity to scale and outliers.
    boundaries=[quantile(reference,i/bins) for i in range(1,bins)]
    def counts(values):
        result=[0]*bins
        for value in values:
            index=0
            while index < len(boundaries) and value > boundaries[index]: index += 1
            result[index]+=1
        total=len(values)
        return [(count/total) for count in result]
    expected=counts(reference); actual=counts(current)
    return sum((a-e)*log((a+epsilon)/(e+epsilon)) for e,a in zip(expected,actual))

def drift_report(reference: Mapping[str,Sequence[float]], current: Mapping[str,Sequence[float]], bins: int = 10) -> dict[str,object]:
    missing=sorted(set(reference)-set(current)); unexpected=sorted(set(current)-set(reference)); metrics={}
    for feature in sorted(set(reference)&set(current)):
        metrics[feature]={"psi":population_stability_index(reference[feature],current[feature],bins=bins),"reference_n":len(reference[feature]),"current_n":len(current[feature])}
    return {"metrics":metrics,"missing_features":missing,"unexpected_features":unexpected,"interpretation":"PSI is a drift indicator, not a model performance metric."}
