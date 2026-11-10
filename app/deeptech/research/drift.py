"""Data and prediction drift diagnostics with transparent formulae."""
from __future__ import annotations
from math import log, isfinite
from typing import Iterable, Sequence
from .statistics import quantile

def population_stability_index(reference: Iterable[float],current: Iterable[float],bins: int=10,epsilon: float=1e-6) -> float:
    ref=list(map(float,reference)); cur=list(map(float,current))
    if len(ref)<2 or len(cur)<2 or bins<2: raise ValueError("samples >= 2 and bins >= 2 required")
    if epsilon<=0: raise ValueError("epsilon must be positive")
    cuts=[quantile(ref,i/bins) for i in range(1,bins)]
    def counts(data):
        result=[0]*bins
        for value in data:
            index=0
            while index<len(cuts) and value>cuts[index]: index+=1
            result[index]+=1
        return result
    a=counts(ref); b=counts(cur); total_a=sum(a); total_b=sum(b); psi=0.0
    for x,y in zip(a,b):
        p=max(epsilon,x/total_a); q=max(epsilon,y/total_b); psi+=(q-p)*log(q/p)
    return psi

def categorical_psi(reference: Iterable[str],current: Iterable[str],categories: Sequence[str],epsilon: float=1e-6) -> float:
    a=list(reference); b=list(current)
    if not a or not b or not categories: raise ValueError("non-empty samples and categories required")
    if epsilon<=0: raise ValueError("epsilon must be positive")
    result=0.0
    for category in categories:
        p=max(epsilon,sum(x==category for x in a)/len(a)); q=max(epsilon,sum(x==category for x in b)/len(b))
        result+=(q-p)*log(q/p)
    return result

def prediction_shift(reference: Iterable[float],current: Iterable[float]) -> dict:
    a=list(map(float,reference)); b=list(map(float,current))
    if not a or not b: raise ValueError("both prediction samples required")
    from .statistics import mean, standard_deviation
    return {"reference_mean":mean(a),"current_mean":mean(b),"mean_delta":mean(b)-mean(a),"reference_std":standard_deviation(a,False),"current_std":standard_deviation(b,False),"sample_sizes":{"reference":len(a),"current":len(b)}}
