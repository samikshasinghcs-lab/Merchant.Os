"""Demand estimation and service-level planning helpers."""
from __future__ import annotations
from dataclasses import dataclass
from math import sqrt
from typing import Sequence
from .statistics import mean, standard_deviation

@dataclass(frozen=True, slots=True)
class DemandForecast:
    expected_demand: float
    standard_deviation: float
    lower_bound: float
    upper_bound: float
    method: str

class DemandEstimator:
    def summarize(self,history: Sequence[float],z: float=1.96) -> DemandForecast:
        values=list(map(float,history))
        if len(values)<2 or any(v<0 for v in values) or z<=0: raise ValueError("at least two non-negative observations and positive z required")
        center=mean(values); spread=standard_deviation(values)
        return DemandForecast(center,spread,max(0,center-z*spread),center+z*spread,"historical normal approximation")
    def weighted_moving_average(self,history: Sequence[float],weights: Sequence[float]) -> float:
        if len(history)!=len(weights) or not history or any(w<0 for w in weights) or sum(weights)<=0: raise ValueError("invalid weighted average inputs")
        return sum(float(x)*float(w) for x,w in zip(history,weights))/sum(weights)
    def exponential_smoothing(self,history: Sequence[float],alpha: float=.3) -> float:
        if not history or not 0<alpha<=1: raise ValueError("history and alpha in (0,1] required")
        state=float(history[0])
        for value in history[1:]: state=alpha*float(value)+(1-alpha)*state
        return state
    def intermittent_demand_rate(self,periods: Sequence[float]) -> float:
        if not periods or any(v<0 for v in periods): raise ValueError("non-negative periods required")
        return sum(v>0 for v in periods)/len(periods)
