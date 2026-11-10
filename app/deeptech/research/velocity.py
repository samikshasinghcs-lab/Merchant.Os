"""Velocity and burst detection for transaction streams."""
from __future__ import annotations
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from threading import RLock
from typing import Deque

@dataclass(frozen=True, slots=True)
class VelocitySnapshot:
    entity_id: str
    window_seconds: float
    event_count: int
    amount_total: float
    first_event: datetime|None
    last_event: datetime|None

class SlidingVelocityCounter:
    def __init__(self,window: timedelta,max_events: int=100000):
        if window.total_seconds()<=0 or max_events<1: raise ValueError("invalid window or capacity")
        self.window=window; self.max_events=max_events; self._events:dict[str,Deque[tuple[datetime,float]]]={}; self._lock=RLock()
    def add(self,entity_id: str,occurred_at: datetime,amount: float=0.0) -> VelocitySnapshot:
        if not entity_id or occurred_at.tzinfo is None: raise ValueError("entity and timezone-aware timestamp required")
        value=float(amount)
        if value<0 or not __import__("math").isfinite(value): raise ValueError("amount must be finite and non-negative")
        stamp=occurred_at.astimezone(timezone.utc)
        with self._lock:
            queue=self._events.setdefault(entity_id,deque())
            if queue and stamp<queue[-1][0]: raise ValueError("events must arrive in chronological order per entity")
            queue.append((stamp,value)); self._prune(queue,stamp)
            while len(queue)>self.max_events: queue.popleft()
            return self._snapshot(entity_id,queue)
    def _prune(self,queue,now):
        cutoff=now-self.window
        while queue and queue[0][0]<cutoff: queue.popleft()
    def _snapshot(self,entity,queue):
        return VelocitySnapshot(entity,self.window.total_seconds(),len(queue),sum(v for _,v in queue),queue[0][0] if queue else None,queue[-1][0] if queue else None)
    def snapshot(self,entity_id: str,now: datetime) -> VelocitySnapshot:
        if now.tzinfo is None: raise ValueError("now must be timezone-aware")
        with self._lock:
            queue=self._events.setdefault(entity_id,deque()); self._prune(queue,now.astimezone(timezone.utc)); return self._snapshot(entity_id,queue)
    def clear(self,entity_id: str|None=None) -> None:
        with self._lock:
            if entity_id is None: self._events.clear()
            else: self._events.pop(entity_id,None)
