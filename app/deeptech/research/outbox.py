"""Transactional-outbox state model for reliable event publication prototypes."""
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timezone
from threading import RLock
from typing import Mapping, Any

@dataclass(frozen=True, slots=True)
class OutboxMessage:
    message_id: str
    tenant_id: str
    topic: str
    payload: Mapping[str,Any]
    created_at: datetime
    attempts: int=0
    published_at: datetime|None=None
    last_error: str|None=None

class InMemoryOutbox:
    """Reference semantics only; durable guarantees require a DB transaction."""
    def __init__(self): self._messages={}; self._lock=RLock()
    def enqueue(self,message_id: str,tenant_id: str,topic: str,payload: Mapping[str,Any],created_at: datetime|None=None) -> OutboxMessage:
        stamp=created_at or datetime.now(timezone.utc)
        if not all((message_id,tenant_id,topic)) or stamp.tzinfo is None: raise ValueError("message identity and aware timestamp required")
        with self._lock:
            if message_id in self._messages: raise ValueError("duplicate outbox message")
            row=OutboxMessage(message_id,tenant_id,topic,dict(payload),stamp); self._messages[message_id]=row; return row
    def pending(self,limit: int=100) -> tuple[OutboxMessage,...]:
        if limit<1: raise ValueError("limit must be positive")
        with self._lock: return tuple(row for row in self._messages.values() if row.published_at is None)[:limit]
    def mark_published(self,message_id: str,when: datetime|None=None) -> OutboxMessage:
        stamp=when or datetime.now(timezone.utc)
        if stamp.tzinfo is None: raise ValueError("timestamp must be timezone-aware")
        with self._lock:
            row=self._messages[message_id]
            updated=OutboxMessage(row.message_id,row.tenant_id,row.topic,row.payload,row.created_at,row.attempts+1,stamp,None); self._messages[message_id]=updated; return updated
    def mark_failed(self,message_id: str,error: str) -> OutboxMessage:
        with self._lock:
            row=self._messages[message_id]; updated=OutboxMessage(row.message_id,row.tenant_id,row.topic,row.payload,row.created_at,row.attempts+1,None,str(error)[:500]); self._messages[message_id]=updated; return updated
