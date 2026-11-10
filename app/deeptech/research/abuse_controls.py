"""Rate and burst controls for expensive analytical endpoints."""
from __future__ import annotations
from collections import deque
from datetime import datetime, timedelta, timezone
from threading import RLock

class SlidingWindowLimiter:
    def __init__(self,limit: int,window: timedelta):
        if limit<1 or window.total_seconds()<=0: raise ValueError("invalid rate limit")
        self.limit=limit; self.window=window; self._requests={}; self._lock=RLock()
    def allow(self,tenant_id: str,now: datetime|None=None) -> bool:
        if not tenant_id: raise ValueError("tenant required")
        stamp=now or datetime.now(timezone.utc)
        if stamp.tzinfo is None: raise ValueError("timestamp must be timezone-aware")
        stamp=stamp.astimezone(timezone.utc); cutoff=stamp-self.window
        with self._lock:
            queue=self._requests.setdefault(tenant_id,deque())
            while queue and queue[0]<cutoff: queue.popleft()
            if len(queue)>=self.limit: return False
            queue.append(stamp); return True
    def remaining(self,tenant_id: str,now: datetime|None=None) -> int:
        stamp=now or datetime.now(timezone.utc)
        if stamp.tzinfo is None: raise ValueError("timestamp must be timezone-aware")
        cutoff=stamp.astimezone(timezone.utc)-self.window
        with self._lock:
            queue=self._requests.setdefault(tenant_id,deque())
            while queue and queue[0]<cutoff: queue.popleft()
            return max(0,self.limit-len(queue))
