"""Interpretable forecasting baselines with chronological evaluation support."""
from __future__ import annotations
from dataclasses import dataclass
from math import sqrt
from typing import Iterable, Sequence
from .statistics import mean, quantile

@dataclass(frozen=True, slots=True)
class Forecast:
    values: tuple[float,...]
    lower: tuple[float,...]
    upper: tuple[float,...]
    method: str
    metadata: dict

class NaiveForecaster:
    def forecast(self,history: Sequence[float],horizon: int) -> Forecast:
        if not history or horizon<1: raise ValueError("history and positive horizon required")
        last=float(history[-1]); return Forecast((last,)*horizon,(last,)*horizon,(last,)*horizon,"naive",{"history_size":len(history)})

class MovingAverageForecaster:
    def __init__(self,window: int=7) -> None:
        if window<1: raise ValueError("window must be positive")
        self.window=window
    def forecast(self,history: Sequence[float],horizon: int) -> Forecast:
        if len(history)<self.window or horizon<1: raise ValueError("insufficient history or invalid horizon")
        tail=[float(x) for x in history[-self.window:]]; value=mean(tail)
        residual=[x-value for x in tail]; spread=(sum(x*x for x in residual)/max(1,len(residual)-1))**.5
        values=[]; lower=[]; upper=[]
        for step in range(1,horizon+1):
            values.append(value); margin=1.96*spread*(step**.5); lower.append(value-margin); upper.append(value+margin)
        return Forecast(tuple(values),tuple(lower),tuple(upper),"moving_average",{"window":self.window,"residual_scale":spread,"interval":"normal approximation; not guaranteed"})

class SimpleExponentialSmoothing:
    def __init__(self,alpha: float=.3) -> None:
        if not 0<alpha<=1: raise ValueError("alpha must be in (0, 1]")
        self.alpha=alpha
    def fit_level(self,history: Sequence[float]) -> float:
        if not history: raise ValueError("history required")
        level=float(history[0])
        for value in history[1:]: level=self.alpha*float(value)+(1-self.alpha)*level
        return level
    def forecast(self,history: Sequence[float],horizon: int) -> Forecast:
        if horizon<1: raise ValueError("horizon must be positive")
        level=self.fit_level(history); residuals=[]; state=float(history[0])
        for value in history[1:]:
            residuals.append(float(value)-state); state=self.alpha*float(value)+(1-self.alpha)*state
        sigma=sqrt(sum(x*x for x in residuals)/max(1,len(residuals)-1)) if residuals else 0.0
        values=tuple(level for _ in range(horizon)); margins=tuple(1.96*sigma*(i+1)**.5 for i in range(horizon))
        return Forecast(values,tuple(v-m for v,m in zip(values,margins)),tuple(v+m for v,m in zip(values,margins)),"simple_exponential_smoothing",{"alpha":self.alpha,"level":level,"interval":"approximate"})

def mean_absolute_error(actual: Iterable[float],predicted: Iterable[float]) -> float:
    a=list(map(float,actual)); p=list(map(float,predicted))
    if not a or len(a)!=len(p): raise ValueError("equal non-empty sequences required")
    return mean([abs(x-y) for x,y in zip(a,p)])

def root_mean_squared_error(actual: Iterable[float],predicted: Iterable[float]) -> float:
    a=list(map(float,actual)); p=list(map(float,predicted))
    if not a or len(a)!=len(p): raise ValueError("equal non-empty sequences required")
    return mean([(x-y)**2 for x,y in zip(a,p)])**.5

def mean_absolute_percentage_error(actual: Iterable[float],predicted: Iterable[float],epsilon: float=1e-8) -> float:
    a=list(map(float,actual)); p=list(map(float,predicted))
    if not a or len(a)!=len(p): raise ValueError("equal non-empty sequences required")
    return mean([abs(x-y)/max(abs(x),epsilon) for x,y in zip(a,p)])

def chronological_split(values: Sequence[float],train_fraction: float=.8) -> tuple[list[float],list[float]]:
    if not 0<train_fraction<1: raise ValueError("train_fraction must be in (0,1)")
    cut=int(len(values)*train_fraction)
    if cut<1 or cut>=len(values): raise ValueError("not enough observations to split")
    return list(values[:cut]),list(values[cut:])
