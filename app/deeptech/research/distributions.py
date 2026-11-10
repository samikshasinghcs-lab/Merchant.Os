"""Distribution utilities for transparent uncertainty modelling."""
from __future__ import annotations
from dataclasses import dataclass
from math import exp, log, sqrt, pi
from random import Random
from typing import Iterable, Sequence
from .statistics import mean, quantile

@dataclass(frozen=True, slots=True)
class DistributionSummary:
    count: int
    mean: float
    variance: float
    minimum: float
    q05: float
    median: float
    q95: float
    maximum: float

def summarize(values: Iterable[float]) -> DistributionSummary:
    data=sorted(float(x) for x in values)
    if not data: raise ValueError("values required")
    if any(not __import__("math").isfinite(x) for x in data): raise ValueError("finite values required")
    center=mean(data); variance=sum((x-center)**2 for x in data)/len(data)
    return DistributionSummary(len(data),center,variance,data[0],quantile(data,.05),quantile(data,.5),quantile(data,.95),data[-1])

class EmpiricalDistribution:
    def __init__(self,values: Iterable[float]):
        self.values=tuple(sorted(float(x) for x in values))
        if not self.values: raise ValueError("empirical sample required")
    def cdf(self,x: float) -> float: return sum(v<=x for v in self.values)/len(self.values)
    def quantile(self,q: float) -> float: return quantile(self.values,q)
    def sample(self,rng: Random) -> float: return self.values[rng.randrange(len(self.values))]
    def bootstrap_mean(self,iterations: int=1000,seed: int=1) -> tuple[float,...]:
        if iterations<1: raise ValueError("iterations must be positive")
        rng=Random(seed); n=len(self.values)
        return tuple(sum(self.values[rng.randrange(n)] for _ in range(n))/n for _ in range(iterations))

class TriangularDistribution:
    def __init__(self,low: float,mode: float,high: float):
        if not low<=mode<=high or low==high: raise ValueError("require low <= mode <= high and low < high")
        self.low=float(low); self.mode=float(mode); self.high=float(high)
    def sample(self,rng: Random) -> float: return rng.triangular(self.low,self.high,self.mode)
    def mean(self) -> float: return (self.low+self.mode+self.high)/3
    def variance(self) -> float: return (self.low**2+self.mode**2+self.high**2-self.low*self.mode-self.low*self.high-self.mode*self.high)/18
    def cdf(self,x: float) -> float:
        if x<=self.low: return 0.0
        if x>=self.high: return 1.0
        if x<=self.mode: return (x-self.low)**2/((self.high-self.low)*(self.mode-self.low))
        return 1-(self.high-x)**2/((self.high-self.low)*(self.high-self.mode))

class BernoulliDistribution:
    def __init__(self,p: float):
        if not 0<=p<=1: raise ValueError("p must be in [0,1]")
        self.p=float(p)
    def sample(self,rng: Random) -> int: return int(rng.random()<self.p)
    def mean(self) -> float: return self.p
    def variance(self) -> float: return self.p*(1-self.p)
    def likelihood(self,outcome: int) -> float:
        if outcome not in (0,1): raise ValueError("outcome must be binary")
        return self.p if outcome else 1-self.p
