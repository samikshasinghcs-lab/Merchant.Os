"""Model governance metadata, approvals, and reproducibility manifests."""
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime, timezone
from hashlib import sha256
import json
from typing import Any, Mapping, Sequence

@dataclass(frozen=True, slots=True)
class ModelCard:
    name: str
    version: str
    purpose: str
    owner: str
    training_window: str
    intended_use: tuple[str,...]
    prohibited_use: tuple[str,...]
    limitations: tuple[str,...]
    feature_names: tuple[str,...]
    metrics: Mapping[str,float] = field(default_factory=dict)
    def __post_init__(self) -> None:
        if not all((self.name,self.version,self.purpose,self.owner)): raise ValueError("model identity and purpose required")
        if set(self.intended_use)&set(self.prohibited_use): raise ValueError("intended and prohibited uses overlap")
        if any(not 0<=float(v)<=1 for k,v in self.metrics.items() if k.endswith("_rate")): raise ValueError("rate metrics must be in [0,1]")
    def digest(self) -> str:
        payload={"name":self.name,"version":self.version,"purpose":self.purpose,"owner":self.owner,"training_window":self.training_window,"intended_use":self.intended_use,"prohibited_use":self.prohibited_use,"limitations":self.limitations,"feature_names":self.feature_names,"metrics":dict(self.metrics)}
        return sha256(json.dumps(payload,sort_keys=True,separators=(",",":"),default=str).encode()).hexdigest()

@dataclass(frozen=True, slots=True)
class Approval:
    model_digest: str
    reviewer: str
    approved_at: datetime
    scope: str
    expires_at: datetime|None = None
    def valid_at(self,when: datetime) -> bool:
        if when.tzinfo is None: raise ValueError("time must be timezone-aware")
        if self.approved_at>when: return False
        return self.expires_at is None or when<self.expires_at

class ModelRegistry:
    def __init__(self) -> None: self._cards={}; self._approvals={}
    def register(self,card: ModelCard) -> str:
        key=(card.name,card.version)
        if key in self._cards: raise ValueError("model version already registered")
        digest=card.digest(); self._cards[key]=(card,digest); return digest
    def approve(self,name: str,version: str,reviewer: str,scope: str,expires_at: datetime|None=None,approved_at: datetime|None=None) -> Approval:
        card,digest=self._cards[(name,version)]
        if not reviewer or not scope: raise ValueError("reviewer and scope required")
        approval=Approval(digest,reviewer,approved_at or datetime.now(timezone.utc),scope,expires_at)
        self._approvals.setdefault((name,version),[]).append(approval); return approval
    def approved(self,name: str,version: str,scope: str,when: datetime|None=None) -> bool:
        _,digest=self._cards[(name,version)]; stamp=when or datetime.now(timezone.utc)
        return any(a.model_digest==digest and a.scope==scope and a.valid_at(stamp) for a in self._approvals.get((name,version),()))
    def card(self,name: str,version: str) -> ModelCard: return self._cards[(name,version)][0]
