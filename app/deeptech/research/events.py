"""In-process deterministic event bus for research workflows and test harnesses."""
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timezone
from threading import RLock
from typing import Callable, Mapping, Any

@dataclass(frozen=True, slots=True)
class DomainEvent:
    event_id: str
    tenant_id: str
    event_type: str
    occurred_at: datetime
    payload: Mapping[str,Any]
    sequence: int

class EventBus:
    def __init__(self) -> None:
        self._handlers:dict[str,list[Callable[[DomainEvent],None]]]={}; self._events=[]; self._ids=set(); self._lock=RLock()
    def subscribe(self,event_type: str,handler: Callable[[DomainEvent],None]) -> None:
        if not event_type or not callable(handler): raise ValueError("event type and callable handler required")
        with self._lock: self._handlers.setdefault(event_type,[]).append(handler)
    def publish(self,event_id: str,tenant_id: str,event_type: str,payload: Mapping[str,Any],occurred_at: datetime|None=None) -> DomainEvent:
        if not all((event_id,tenant_id,event_type)): raise ValueError("event identity required")
        stamp=occurred_at or datetime.now(timezone.utc)
        if stamp.tzinfo is None: raise ValueError("timestamp must be timezone-aware")
        with self._lock:
            if event_id in self._ids: raise ValueError("duplicate event id")
            event=DomainEvent(event_id,tenant_id,event_type,stamp,dict(payload),len(self._events)+1)
            handlers=tuple(self._handlers.get(event_type,()))
            self._events.append(event); self._ids.add(event_id)
        failures=[]
        for handler in handlers:
            try: handler(event)
            except Exception as exc: failures.append(exc)
        if failures: raise RuntimeError(f"{len(failures)} event handler(s) failed after event was recorded") from failures[0]
        return event
    def history(self,tenant_id: str,event_type: str|None=None) -> tuple[DomainEvent,...]:
        with self._lock: return tuple(e for e in self._events if e.tenant_id==tenant_id and (event_type is None or e.event_type==event_type))
