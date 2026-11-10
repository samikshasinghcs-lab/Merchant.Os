"""Score normalization and monotonic transformations for interpretable models."""
from __future__ import annotations
from math import exp, log, isfinite
from typing import Iterable, Sequence

def min_max(values: Iterable[float],lower: float=0.0,upper: float=1.0) -> list[float]:
    data=list(map(float,values))
    if not data or lower>=upper or any(not isfinite(v) for v in data): raise ValueError("invalid normalization input")
    lo=min(data); hi=max(data)
    if hi==lo: return [(lower+upper)/2 for _ in data]
    return [lower+(v-lo)/(hi-lo)*(upper-lower) for v in data]

def sigmoid(value: float) -> float:
    x=float(value)
    if x>=0: return 1/(1+exp(-x))
    e=exp(x); return e/(1+e)

def logit(probability: float,epsilon: float=1e-12) -> float:
    p=float(probability)
    if not 0<=p<=1: raise ValueError("probability must be in [0,1]")
    p=min(1-epsilon,max(epsilon,p)); return log(p/(1-p))

def softmax(values: Sequence[float],temperature: float=1.0) -> tuple[float,...]:
    if not values or temperature<=0: raise ValueError("values and positive temperature required")
    shifted=[float(v)/temperature for v in values]; maximum=max(shifted); exps=[exp(v-maximum) for v in shifted]; total=sum(exps)
    return tuple(v/total for v in exps)

def weighted_score(signals: Iterable[tuple[float,float]]) -> float:
    rows=list(signals)
    if not rows or any(weight<0 or not 0<=value<=1 for value,weight in rows): raise ValueError("invalid weighted signals")
    total=sum(weight for _,weight in rows)
    if total==0: raise ValueError("positive total weight required")
    return sum(value*weight for value,weight in rows)/total
