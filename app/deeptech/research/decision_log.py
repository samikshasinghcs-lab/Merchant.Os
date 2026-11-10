"""Decision records that preserve model, policy, and human-review provenance."""
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
import json
from typing import Any, Mapping

@dataclass(frozen=True, slots=True)
class DecisionRecord:
    decision_id: str
    tenant_id: str
    subject_id: str
    decision_type: str
    recommendation: str
    model_version: str
    policy_version: str
    created_at: datetime
    evidence: Mapping[str,Any]
    human_disposition: str|None=None
    reviewer_id: str|None=None
    def __post_init__(self):
        if not all((self.decision_id,self.tenant_id,self.subject_id,self.decision_type,self.recommendation)): raise ValueError("decision identity required")
        if self.created_at.tzinfo is None: raise ValueError("created_at must be timezone-aware")
        if self.human_disposition and not self.reviewer_id: raise ValueError("reviewer required for human disposition")
    def fingerprint(self) -> str:
        body={"decision_id":self.decision_id,"tenant_id":self.tenant_id,"subject_id":self.subject_id,"decision_type":self.decision_type,"recommendation":self.recommendation,"model_version":self.model_version,"policy_version":self.policy_version,"created_at":self.created_at.astimezone(timezone.utc).isoformat(),"evidence":dict(self.evidence),"human_disposition":self.human_disposition,"reviewer_id":self.reviewer_id}
        return sha256(json.dumps(body,sort_keys=True,separators=(",",":"),default=str).encode()).hexdigest()

class DecisionLog:
    def __init__(self,tenant_id: str): self.tenant_id=tenant_id; self._records={}
    def append(self,record: DecisionRecord) -> str:
        if record.tenant_id!=self.tenant_id: raise PermissionError("cross-tenant decision record")
        if record.decision_id in self._records: raise ValueError("duplicate decision id")
        digest=record.fingerprint(); self._records[record.decision_id]=(record,digest); return digest
    def get(self,decision_id: str) -> DecisionRecord|None:
        item=self._records.get(decision_id); return item[0] if item else None
    def verify(self) -> bool: return all(record.fingerprint()==digest for record,digest in self._records.values())
    def list(self) -> tuple[DecisionRecord,...]: return tuple(item[0] for item in self._records.values())
