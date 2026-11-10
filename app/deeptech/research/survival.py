"""Non-parametric survival summaries for time-to-dispute and resolution analysis."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Iterable, Sequence

@dataclass(frozen=True, slots=True)
class SurvivalPoint:
    time: float
    at_risk: int
    events: int
    censored: int
    survival: float

class KaplanMeier:
    def fit(self,durations: Iterable[float],events: Iterable[int]) -> tuple[SurvivalPoint,...]:
        times=list(map(float,durations)); observed=list(map(int,events))
        if not times or len(times)!=len(observed) or any(t<0 for t in times) or any(e not in (0,1) for e in observed): raise ValueError("invalid survival data")
        unique=sorted(set(times)); at_risk=len(times); survival=1.0; points=[]
        for stamp in unique:
            count=sum(t==stamp for t in times); deaths=sum(t==stamp and e==1 for t,e in zip(times,observed)); censored=count-deaths
            if at_risk and deaths: survival*=1-deaths/at_risk
            points.append(SurvivalPoint(stamp,at_risk,deaths,censored,survival)); at_risk-=count
        return tuple(points)
    def median_survival(self,curve: Sequence[SurvivalPoint]) -> float|None:
        return next((point.time for point in curve if point.survival<=.5),None)
    def survival_at(self,curve: Sequence[SurvivalPoint],time: float) -> float:
        eligible=[point for point in curve if point.time<=time]
        return eligible[-1].survival if eligible else 1.0

def incidence_by_horizon(durations: Iterable[float],events: Iterable[int],horizon: float) -> float:
    times=list(map(float,durations)); flags=list(map(int,events))
    if len(times)!=len(flags) or not times: raise ValueError("paired survival data required")
    return sum(t<=horizon and e==1 for t,e in zip(times,flags))/len(times)
