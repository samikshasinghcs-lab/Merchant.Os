"""Privacy primitives for analytics minimisation; not a full anonymisation claim."""
from __future__ import annotations
from hashlib import sha256, hmac
import secrets
from typing import Iterable, Mapping

class Pseudonymizer:
    def __init__(self,key: bytes) -> None:
        if len(key)<16: raise ValueError("pseudonymization key must be at least 16 bytes")
        self._key=bytes(key)
    def transform(self,tenant_id: str,subject_id: str,namespace: str="subject") -> str:
        if not tenant_id or not subject_id or not namespace: raise ValueError("scope and subject required")
        message=f"{tenant_id}|{namespace}|{subject_id}".encode()
        return hmac.new(self._key,message,sha256).hexdigest()
    def rotate(self,new_key: bytes) -> "Pseudonymizer": return Pseudonymizer(new_key)

class DataMinimizer:
    DEFAULT_DENY={"email","phone","address","full_name","card_number","cvv","password","access_token","refresh_token"}
    def __init__(self,allowlist: Iterable[str],denylist: Iterable[str]=()) -> None:
        self.allowlist=set(allowlist); self.denylist=self.DEFAULT_DENY|set(denylist)
        if self.allowlist & self.denylist: raise ValueError("allowlist conflicts with denylist")
    def project(self,record: Mapping[str,object]) -> dict[str,object]:
        return {key:value for key,value in record.items() if key in self.allowlist and key not in self.denylist}
    def audit_removed(self,record: Mapping[str,object]) -> tuple[str,...]:
        return tuple(sorted(set(record)-set(self.project(record))))

class ConsentLedger:
    """In-memory consent state model for tests and prototypes; persist externally."""
    def __init__(self) -> None: self._states={}
    def grant(self,tenant_id: str,subject_id: str,purpose: str,version: str) -> None:
        if not all((tenant_id,subject_id,purpose,version)): raise ValueError("consent scope required")
        self._states[(tenant_id,subject_id,purpose)]={"granted":True,"version":version}
    def revoke(self,tenant_id: str,subject_id: str,purpose: str) -> None:
        self._states[(tenant_id,subject_id,purpose)]={"granted":False,"version":None}
    def allowed(self,tenant_id: str,subject_id: str,purpose: str) -> bool:
        return bool(self._states.get((tenant_id,subject_id,purpose),{}).get("granted",False))
    def export(self) -> dict:
        return {"|".join(key):dict(value) for key,value in sorted(self._states.items())}

def generate_secret(length: int=32) -> bytes:
    if length<16: raise ValueError("secret length must be >= 16")
    return secrets.token_bytes(length)
