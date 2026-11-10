"""Numerically careful descriptive and robust statistics (stdlib only)."""
from __future__ import annotations
from math import sqrt, isfinite
from statistics import median
from typing import Iterable, Sequence

def clean(values: Iterable[float]) -> list[float]:
    result = [float(v) for v in values]
    if not result: raise ValueError("at least one observation is required")
    if any(not isfinite(v) for v in result): raise ValueError("observations must be finite")
    return result

def mean(values: Iterable[float]) -> float:
    data = clean(values)
    return sum(data) / len(data)

def variance(values: Iterable[float], sample: bool = True) -> float:
    data = clean(values)
    if sample and len(data) < 2: raise ValueError("sample variance needs two observations")
    center = sum(data) / len(data)
    denominator = len(data) - 1 if sample else len(data)
    return sum((x-center)**2 for x in data) / denominator

def standard_deviation(values: Iterable[float], sample: bool = True) -> float:
    return sqrt(variance(values, sample=sample))

def quantile(values: Iterable[float], q: float) -> float:
    data = sorted(clean(values))
    if not 0 <= q <= 1: raise ValueError("q must be in [0, 1]")
    position = (len(data)-1)*q
    lower = int(position); upper = min(lower+1, len(data)-1)
    fraction = position-lower
    return data[lower]*(1-fraction) + data[upper]*fraction

def percentile_rank(values: Iterable[float], value: float) -> float:
    data = clean(values); x=float(value)
    return sum(item <= x for item in data) / len(data)

def median_absolute_deviation(values: Iterable[float]) -> float:
    data=clean(values); center=median(data)
    return float(median([abs(x-center) for x in data]))

def robust_z_score(values: Iterable[float], value: float) -> float:
    data=clean(values); mad=median_absolute_deviation(data)
    if mad == 0:
        spread=standard_deviation(data, sample=False)
        return 0.0 if spread == 0 else (float(value)-mean(data))/spread
    return 0.6744897501960817*(float(value)-median(data))/mad

def covariance(left: Iterable[float], right: Iterable[float]) -> float:
    x=clean(left); y=clean(right)
    if len(x)!=len(y) or len(x)<2: raise ValueError("equal samples of size >= 2 required")
    mx=sum(x)/len(x); my=sum(y)/len(y)
    return sum((a-mx)*(b-my) for a,b in zip(x,y))/(len(x)-1)

def correlation(left: Iterable[float], right: Iterable[float]) -> float:
    x=clean(left); y=clean(right)
    sx=standard_deviation(x); sy=standard_deviation(y)
    if sx==0 or sy==0: return 0.0
    return max(-1.0,min(1.0,covariance(x,y)/(sx*sy)))

def rank(values: Sequence[float]) -> list[float]:
    indexed=sorted(enumerate(values), key=lambda pair: pair[1]); output=[0.0]*len(indexed)
    i=0
    while i<len(indexed):
        j=i+1
        while j<len(indexed) and indexed[j][1]==indexed[i][1]: j+=1
        average=(i+1+j)/2
        for k in range(i,j): output[indexed[k][0]]=average
        i=j
    return output

def spearman(left: Iterable[float], right: Iterable[float]) -> float:
    x=clean(left); y=clean(right)
    if len(x)!=len(y) or len(x)<2: raise ValueError("equal samples of size >= 2 required")
    return correlation(rank(x),rank(y))

def ewma(values: Iterable[float], alpha: float) -> list[float]:
    data=clean(values)
    if not 0 < alpha <= 1: raise ValueError("alpha must be in (0, 1]")
    result=[]; state=data[0]
    for value in data:
        state=alpha*value+(1-alpha)*state; result.append(state)
    return result

def winsorize(values: Iterable[float], lower_q: float=.05, upper_q: float=.95) -> list[float]:
    data=clean(values)
    if not 0 <= lower_q <= upper_q <= 1: raise ValueError("invalid quantile bounds")
    lo=quantile(data,lower_q); hi=quantile(data,upper_q)
    return [min(hi,max(lo,x)) for x in data]

def trimmed_mean(values: Iterable[float], proportion: float=.1) -> float:
    data=sorted(clean(values))
    if not 0 <= proportion < .5: raise ValueError("proportion must be in [0, .5)")
    cut=int(len(data)*proportion); retained=data[cut:len(data)-cut] if cut else data
    return sum(retained)/len(retained)

def coefficient_of_variation(values: Iterable[float]) -> float:
    data=clean(values); center=mean(data)
    if center==0: return 0.0 if standard_deviation(data,False)==0 else float("inf")
    return standard_deviation(data,False)/abs(center)
