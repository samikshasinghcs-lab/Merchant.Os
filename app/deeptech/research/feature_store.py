"""Versioned in-memory feature store with point-in-time retrieval safeguards."""
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timezone
from threading import RLock
from typing import Mapping

@dataclass(frozen=True, slots=True)
class StoredFeature:
    tenant_id: str
    entity_id: str
    feature_name: str
    value: float|str|int|bool
    event_time: datetime
    ingestion_time: datetime
    version: int

class FeatureStore:
    def __init__(self) -> None: self._rows:dict[tuple[str,str,str],list[StoredFeature]]={}; self._lock=RLock()
    def put(self,tenant_id: str,entity_id: str,feature_name: str,value,event_time: datetime,ingestion_time: datetime|None=None) -> StoredFeature:
        if not all((tenant_id,entity_id,feature_name)) or event_time.tzinfo is None: raise ValueError("tenant, entity, feature and aware event time required")
        ingested=ingestion_time or datetime.now(timezone.utc)
        if ingested.tzinfo is None: raise ValueError("ingestion time must be timezone-aware")
        key=(tenant_id,entity_id,feature_name)
        with self._lock:
            rows=self._rows.setdefault(key,[]); version=len(rows)+1
            row=StoredFeature(tenant_id,entity_id,feature_name,value,event_time,ingested,version); rows.append(row); return row
    def get_latest(self,tenant_id: str,entity_id: str,feature_name: str,as_of: datetime|None=None) -> StoredFeature|None:
        key=(tenant_id,entity_id,feature_name); cutoff=as_of
        if cutoff is not None and cutoff.tzinfo is None: raise ValueError("as_of must be timezone-aware")
        with self._lock:
            rows=self._rows.get(key,())
            eligible=[row for row in rows if cutoff is None or (row.event_time<=cutoff and row.ingestion_time<=cutoff)]
            return max(eligible,key=lambda row:(row.event_time,row.version),default=None)
    def get_many(self,tenant_id: str,entity_id: str,as_of: datetime|None=None) -> Mapping[str,StoredFeature]:
        names={name for t,e,name in self._rows if t==tenant_id and e==entity_id}
        return {name:row for name in sorted(names) if (row:=self.get_latest(tenant_id,entity_id,name,as_of)) is not None}
    def delete_tenant(self,tenant_id: str) -> int:
        with self._lock:
            keys=[key for key in self._rows if key[0]==tenant_id]
            count=sum(len(self._rows.pop(key)) for key in keys); return count
