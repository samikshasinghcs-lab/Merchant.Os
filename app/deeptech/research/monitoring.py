"""Operational health monitors for data quality, latency, and failure rates."""
from __future__ import annotations
from dataclasses import dataclass
from collections import deque
from datetime import datetime, timezone, timedelta
from threading import RLock
from typing import Mapping

@dataclass(frozen=True, slots=True)
class HealthSnapshot:
    component: str
    sample_count: int
    error_rate: float
    p95_latency_ms: float
    status: str
    observed_at: datetime

class RollingHealthMonitor:
    def __init__(self,component: str,window_size: int=1000,error_threshold: float=.05,latency_threshold_ms: float=1000):
        if not component or window_size<1 or not 0<=error_threshold<=1 or latency_threshold_ms<0: raise ValueError("invalid monitor configuration")
        self.component=component; self.window_size=window_size; self.error_threshold=error_threshold; self.latency_threshold_ms=latency_threshold_ms; self._samples=deque(maxlen=window_size); self._lock=RLock()
    def record(self,latency_ms: float,success: bool,observed_at: datetime|None=None) -> HealthSnapshot:
        value=float(latency_ms)
        if value<0 or not __import__("math").isfinite(value): raise ValueError("latency must be finite and non-negative")
        stamp=observed_at or datetime.now(timezone.utc)
        if stamp.tzinfo is None: raise ValueError("timestamp must be timezone-aware")
        with self._lock:
            self._samples.append((value,bool(success),stamp)); return self.snapshot(stamp)
    def snapshot(self,observed_at: datetime|None=None) -> HealthSnapshot:
        stamp=observed_at or datetime.now(timezone.utc)
        with self._lock:
            rows=list(self._samples); n=len(rows); errors=sum(not ok for _,ok,_ in rows); latencies=sorted(x for x,_,_ in rows)
            p95=latencies[min(n-1,int(.95*(n-1)))] if n else 0.0; rate=errors/n if n else 0.0
            status="healthy" if rate<=self.error_threshold and p95<=self.latency_threshold_ms else "degraded"
            return HealthSnapshot(self.component,n,rate,p95,status,stamp)
    def reset(self) -> None:
        with self._lock: self._samples.clear()
