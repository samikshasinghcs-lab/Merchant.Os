"""Scoped idempotency registry for analytical jobs and command prototypes."""
from __future__ import annotations
from dataclasses import dataclass
from hashlib import sha256
import json
from threading import RLock
from typing import Any, Mapping

@dataclass(frozen=True, slots=True)
class IdempotencyRecord:
    tenant_id: str
    key: str
    request_hash: str
    state: str
    response: Mapping[str,Any]|None

class IdempotencyRegistry:
    def __init__(self): self._records={}; self._lock=RLock()
    def fingerprint(self,payload: Mapping[str,Any]) -> str:
        encoded=json.dumps(payload,sort_keys=True,separators=(",",":"),default=str).encode()
        return sha256(encoded).hexdigest()
    def reserve(self,tenant_id: str,key: str,payload: Mapping[str,Any]) -> tuple[IdempotencyRecord,bool]:
        if not tenant_id or not key: raise ValueError("tenant and idempotency key required")
        digest=self.fingerprint(payload); scope=(tenant_id,key)
        with self._lock:
            existing=self._records.get(scope)
            if existing:
                if existing.request_hash!=digest: raise ValueError("idempotency key reused with different request")
                return existing,False
            record=IdempotencyRecord(tenant_id,key,digest,"reserved",None); self._records[scope]=record; return record,True
    def complete(self,tenant_id: str,key: str,response: Mapping[str,Any]) -> IdempotencyRecord:
        scope=(tenant_id,key)
        with self._lock:
            current=self._records[scope]
            if current.state=="completed":
                if current.response!=dict(response): raise ValueError("completed response cannot be changed")
                return current
            updated=IdempotencyRecord(tenant_id,key,current.request_hash,"completed",dict(response)); self._records[scope]=updated; return updated
    def get(self,tenant_id: str,key: str) -> IdempotencyRecord|None: return self._records.get((tenant_id,key))
