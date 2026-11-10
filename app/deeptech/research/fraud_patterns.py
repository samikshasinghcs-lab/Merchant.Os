"""Rule-based pattern primitives for investigations, not automated fraud verdicts."""
from __future__ import annotations
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Iterable, Mapping, Sequence

@dataclass(frozen=True, slots=True)
class PatternHit:
    pattern: str
    entity_id: str
    observation_ids: tuple[str,...]
    score: float
    explanation: str

class PatternDetector:
    def repeated_amounts(self,rows: Iterable[Mapping],minimum: int=3) -> tuple[PatternHit,...]:
        if minimum<2: raise ValueError("minimum must be >= 2")
        buckets=defaultdict(list)
        for row in rows: buckets[(str(row.get("merchant_id")),str(row.get("amount")),str(row.get("currency")))].append(str(row.get("id")))
        return tuple(PatternHit("REPEATED_AMOUNT",key[0],tuple(ids),min(1,len(ids)/minimum),"same merchant and exact amount recur") for key,ids in sorted(buckets.items()) if len(ids)>=minimum)
    def rapid_retries(self,rows: Iterable[Mapping],window: timedelta=timedelta(minutes=10),minimum: int=3) -> tuple[PatternHit,...]:
        if window.total_seconds()<=0 or minimum<2: raise ValueError("invalid retry parameters")
        grouped=defaultdict(list)
        for row in rows:
            stamp=row["occurred_at"]
            if isinstance(stamp,str): stamp=datetime.fromisoformat(stamp.replace("Z","+00:00"))
            if stamp.tzinfo is None: raise ValueError("timestamps must be timezone-aware")
            grouped[str(row.get("customer_id"))].append((stamp,str(row.get("id"))))
        hits=[]
        for entity,items in grouped.items():
            ordered=sorted(items)
            for start in range(len(ordered)):
                end=start
                while end<len(ordered) and ordered[end][0]-ordered[start][0]<=window: end+=1
                if end-start>=minimum:
                    ids=tuple(item[1] for item in ordered[start:end]); hits.append(PatternHit("RAPID_RETRIES",entity,ids,min(1,(end-start)/minimum),"multiple attempts inside configured window")); break
        return tuple(hits)
    def shared_attributes(self,rows: Iterable[Mapping],attribute: str,minimum_entities: int=3) -> tuple[PatternHit,...]:
        buckets=defaultdict(set); ids=defaultdict(list)
        for row in rows:
            value=row.get(attribute)
            if value is not None: buckets[str(value)].add(str(row.get("customer_id"))); ids[str(value)].append(str(row.get("id")))
        return tuple(PatternHit("SHARED_ATTRIBUTE",value,tuple(ids[value]),min(1,len(entities)/minimum_entities),f"shared {attribute} across entities") for value,entities in sorted(buckets.items()) if len(entities)>=minimum_entities)
