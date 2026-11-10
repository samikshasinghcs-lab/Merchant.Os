"""Tamper-evident append-only audit chain for decision provenance."""
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
import json
from typing import Any, Iterable, Mapping

GENESIS="0"*64
@dataclass(frozen=True, slots=True)
class AuditEvent:
    event_id: str
    tenant_id: str
    event_type: str
    occurred_at: datetime
    actor_id: str
    payload: Mapping[str,Any]
    previous_hash: str
    event_hash: str

class AuditChain:
    def __init__(self,tenant_id: str) -> None:
        if not tenant_id: raise ValueError("tenant_id required")
        self.tenant_id=tenant_id; self._events=[]
    def append(self,event_id: str,event_type: str,actor_id: str,payload: Mapping[str,Any],occurred_at: datetime|None=None) -> AuditEvent:
        if not event_id or not event_type or not actor_id: raise ValueError("event identity required")
        if any(e.event_id==event_id for e in self._events): raise ValueError("duplicate event id")
        stamp=occurred_at or datetime.now(timezone.utc)
        if stamp.tzinfo is None: raise ValueError("timestamp must be timezone-aware")
        previous=self._events[-1].event_hash if self._events else GENESIS
        safe_payload=dict(payload)
        body={"event_id":event_id,"tenant_id":self.tenant_id,"event_type":event_type,"occurred_at":stamp.astimezone(timezone.utc).isoformat(),"actor_id":actor_id,"payload":safe_payload,"previous_hash":previous}
        digest=sha256(json.dumps(body,sort_keys=True,separators=(",",":"),default=str).encode()).hexdigest()
        event=AuditEvent(event_id,self.tenant_id,event_type,stamp.astimezone(timezone.utc),actor_id,safe_payload,previous,digest)
        self._events.append(event); return event
    def verify(self) -> tuple[bool,int|None]:
        previous=GENESIS
        for index,event in enumerate(self._events):
            body={"event_id":event.event_id,"tenant_id":event.tenant_id,"event_type":event.event_type,"occurred_at":event.occurred_at.astimezone(timezone.utc).isoformat(),"actor_id":event.actor_id,"payload":dict(event.payload),"previous_hash":previous}
            digest=sha256(json.dumps(body,sort_keys=True,separators=(",",":"),default=str).encode()).hexdigest()
            if event.previous_hash!=previous or event.event_hash!=digest: return False,index
            previous=event.event_hash
        return True,None
    def events(self) -> tuple[AuditEvent,...]: return tuple(self._events)
    def export(self) -> list[dict[str,Any]]:
        return [{"event_id":e.event_id,"tenant_id":e.tenant_id,"event_type":e.event_type,"occurred_at":e.occurred_at.isoformat(),"actor_id":e.actor_id,"payload":dict(e.payload),"previous_hash":e.previous_hash,"event_hash":e.event_hash} for e in self._events]
