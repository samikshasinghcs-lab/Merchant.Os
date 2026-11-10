"""Time-series diagnostics: seasonality profiles, lag features, and windows."""
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Iterable, Sequence
from math import sqrt
from .statistics import mean, standard_deviation, correlation

@dataclass(frozen=True, slots=True)
class TimePoint:
    timestamp: datetime
    value: float
    def __post_init__(self):
        if self.timestamp.tzinfo is None: raise ValueError("timestamp must be timezone-aware")
        if not __import__("math").isfinite(float(self.value)): raise ValueError("value must be finite")

class TimeSeries:
    def __init__(self,points: Iterable[TimePoint]):
        self.points=tuple(sorted(points,key=lambda p:p.timestamp))
        if not self.points: raise ValueError("series cannot be empty")
        if len({p.timestamp for p in self.points})!=len(self.points): raise ValueError("duplicate timestamps")
    def values(self): return tuple(float(p.value) for p in self.points)
    def regularize(self,step: timedelta,fill: str="zero") -> "TimeSeries":
        if step.total_seconds()<=0: raise ValueError("step must be positive")
        if fill not in {"zero","forward"}: raise ValueError("unsupported fill strategy")
        lookup={p.timestamp:p.value for p in self.points}; start=self.points[0].timestamp; end=self.points[-1].timestamp
        result=[]; cursor=start; last=0.0
        while cursor<=end:
            if cursor in lookup: last=float(lookup[cursor]); value=last
            else: value=0.0 if fill=="zero" else last
            result.append(TimePoint(cursor,value)); cursor+=step
        return TimeSeries(result)
    def rolling_mean(self,window: int) -> tuple[float,...]:
        if window<1 or window>len(self.points): raise ValueError("invalid window")
        values=self.values(); return tuple(mean(values[i-window+1:i+1]) for i in range(window-1,len(values)))
    def rolling_std(self,window: int) -> tuple[float,...]:
        if window<2 or window>len(self.points): raise ValueError("window must be >=2 and <= series length")
        values=self.values(); return tuple(standard_deviation(values[i-window+1:i+1],False) for i in range(window-1,len(values)))
    def lag(self,periods: int=1) -> tuple[tuple[float,float],...]:
        if periods<1 or periods>=len(self.points): raise ValueError("invalid lag")
        values=self.values(); return tuple((values[i-periods],values[i]) for i in range(periods,len(values)))
    def first_difference(self) -> tuple[float,...]:
        values=self.values(); return tuple(values[i]-values[i-1] for i in range(1,len(values)))
    def seasonal_profile(self,period: int) -> tuple[float,...]:
        if period<1 or len(self.points)<period: raise ValueError("invalid period")
        buckets=[[] for _ in range(period)]
        for i,value in enumerate(self.values()): buckets[i%period].append(value)
        return tuple(mean(bucket) for bucket in buckets)
    def autocorrelation(self,lag: int) -> float:
        pairs=self.lag(lag)
        return correlation([a for a,_ in pairs],[b for _,b in pairs])

def detect_gaps(points: Sequence[TimePoint],expected_step: timedelta) -> tuple[tuple[datetime,datetime],...]:
    if expected_step.total_seconds()<=0: raise ValueError("expected step must be positive")
    ordered=sorted(points,key=lambda p:p.timestamp); gaps=[]
    for left,right in zip(ordered,ordered[1:]):
        if right.timestamp-left.timestamp>expected_step*1.5: gaps.append((left.timestamp,right.timestamp))
    return tuple(gaps)
