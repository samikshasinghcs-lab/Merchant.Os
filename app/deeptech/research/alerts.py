"""Alert lifecycle and deduplication primitives for human review queues."""
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
import json
from typing import Mapping, Any

@dataclass(frozen=True, slots=True)
class Alert:
    alert_id: str
    tenant_id: str
    fingerprint: str
    severity: str
    title: str
    created_at: datetime
    status: str="open"
    assigned_to: str|None=None
    resolution: str|None=None

class AlertManager:
    def __init__(self,tenant_id: str): self.tenant_id=tenant_id; self._alerts={}; self._fingerprints={}
    def fingerprint(self,rule_id: str,subject_id: str,window: str,dimensions: Mapping[str,Any]) -> str:
        payload={"tenant":self.tenant_id,"rule":rule_id,"subject":subject_id,"window":window,"dimensions":dict(dimensions)}
        return sha256(json.dumps(payload,sort_keys=True,separators=(",",":"),default=str).encode()).hexdigest()
    def create(self,alert_id: str,fingerprint: str,severity: str,title: str,created_at: datetime|None=None) -> tuple[Alert,bool]:
        if not all((alert_id,fingerprint,title)) or severity not in {"low","medium","high","critical"}: raise ValueError("invalid alert")
        existing=self._fingerprints.get(fingerprint)
        if existing: return self._alerts[existing],False
        stamp=created_at or datetime.now(timezone.utc)
        if stamp.tzinfo is None: raise ValueError("timestamp must be timezone-aware")
        alert=Alert(alert_id,self.tenant_id,fingerprint,severity,title,stamp); self._alerts[alert_id]=alert; self._fingerprints[fingerprint]=alert_id; return alert,True
    def assign(self,alert_id: str,reviewer: str) -> Alert:
        if not reviewer: raise ValueError("reviewer required")
        current=self._alerts[alert_id]; updated=Alert(current.alert_id,current.tenant_id,current.fingerprint,current.severity,current.title,current.created_at,"assigned",reviewer,current.resolution); self._alerts[alert_id]=updated; return updated
    def resolve(self,alert_id: str,resolution: str,reviewer: str) -> Alert:
        if not resolution or not reviewer: raise ValueError("resolution and reviewer required")
        current=self._alerts[alert_id]; updated=Alert(current.alert_id,current.tenant_id,current.fingerprint,current.severity,current.title,current.created_at,"resolved",reviewer,resolution); self._alerts[alert_id]=updated; return updated
    def list(self,status: str|None=None) -> tuple[Alert,...]:
        return tuple(a for a in self._alerts.values() if status is None or a.status==status)
