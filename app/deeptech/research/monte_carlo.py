"""Monte Carlo estimators with common-random-number scenario comparison."""
from __future__ import annotations
from dataclasses import dataclass
from random import Random
from statistics import mean
from typing import Callable, Iterable, Sequence
from .statistics import quantile

@dataclass(frozen=True, slots=True)
class MonteCarloSummary:
    iterations: int
    mean: float
    standard_error: float
    q01: float
    q05: float
    median: float
    q95: float
    q99: float
    probability_below_zero: float
    seed: int

class MonteCarloEngine:
    def run(self,model: Callable[[Random],float],iterations: int=10000,seed: int=1) -> MonteCarloSummary:
        if iterations<100: raise ValueError("at least 100 iterations required")
        rng=Random(seed); values=[float(model(rng)) for _ in range(iterations)]
        if any(not __import__("math").isfinite(x) for x in values): raise ValueError("simulation produced non-finite values")
        center=mean(values); variance=sum((x-center)**2 for x in values)/(iterations-1)
        return MonteCarloSummary(iterations,center,(variance/iterations)**.5,quantile(values,.01),quantile(values,.05),quantile(values,.5),quantile(values,.95),quantile(values,.99),sum(x<0 for x in values)/iterations,seed)
    def compare_common_random_numbers(self,baseline: Callable[[Random],float],candidate: Callable[[Random],float],iterations: int=10000,seed: int=1) -> dict:
        if iterations<100: raise ValueError("at least 100 iterations required")
        rng=Random(seed); deltas=[]
        for _ in range(iterations):
            state=rng.getstate(); left=float(baseline(rng)); rng.setstate(state); right=float(candidate(rng)); rng.random(); deltas.append(right-left)
        center=mean(deltas); variance=sum((x-center)**2 for x in deltas)/(iterations-1)
        return {"iterations":iterations,"mean_difference":center,"standard_error":(variance/iterations)**.5,"q05":quantile(deltas,.05),"median":quantile(deltas,.5),"q95":quantile(deltas,.95),"seed":seed,"method":"paired common random numbers"}
