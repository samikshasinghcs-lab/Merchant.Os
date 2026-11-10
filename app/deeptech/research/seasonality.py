"""Calendar seasonality profiles with baseline normalization."""
from __future__ import annotations
from collections import defaultdict
from datetime import datetime
from typing import Iterable, Mapping
from .statistics import mean

class SeasonalityAnalyzer:
    def weekday_profile(self,observations: Iterable[tuple[datetime,float]]) -> Mapping[int,float]:
        buckets=defaultdict(list)
        for stamp,value in observations:
            if stamp.tzinfo is None: raise ValueError("timestamps must be timezone-aware")
            buckets[stamp.weekday()].append(float(value))
        return {day:mean(values) for day,values in sorted(buckets.items())}
    def hour_profile(self,observations: Iterable[tuple[datetime,float]]) -> Mapping[int,float]:
        buckets=defaultdict(list)
        for stamp,value in observations:
            if stamp.tzinfo is None: raise ValueError("timestamps must be timezone-aware")
            buckets[stamp.hour].append(float(value))
        return {hour:mean(values) for hour,values in sorted(buckets.items())}
    def index(self,profile: Mapping[int,float]) -> Mapping[int,float]:
        if not profile: raise ValueError("profile required")
        baseline=mean(profile.values())
        if baseline==0: return {key:0.0 for key in profile}
        return {key:float(value)/baseline for key,value in profile.items()}
    def peak_periods(self,profile: Mapping[int,float],top_n: int=3) -> tuple[int,...]:
        if top_n<1: raise ValueError("top_n must be positive")
        return tuple(key for key,_ in sorted(profile.items(),key=lambda item:(-item[1],item[0]))[:top_n])
