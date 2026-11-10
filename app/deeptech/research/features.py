"""Feature extraction with explicit schemas and no hidden network calls."""
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from hashlib import sha256
import json
from math import log1p
from typing import Any, Iterable, Mapping, Sequence
from .types import Observation

@dataclass(frozen=True, slots=True)
class FeatureVector:
    entity_id: str
    merchant_id: str
    timestamp: datetime
    values: Mapping[str, float]
    categorical: Mapping[str, str]
    schema_version: str = "1"
    def __post_init__(self) -> None:
        if self.timestamp.tzinfo is None: raise ValueError("timestamp must be timezone-aware")
        if any(not isinstance(v,(int,float)) for v in self.values.values()): raise ValueError("numeric features required")
        object.__setattr__(self,"values",dict(self.values)); object.__setattr__(self,"categorical",dict(self.categorical))
    def digest(self) -> str:
        payload={"id":self.entity_id,"merchant":self.merchant_id,"timestamp":self.timestamp.astimezone(timezone.utc).isoformat(),"values":dict(sorted(self.values.items())),"categorical":dict(sorted(self.categorical.items())),"schema":self.schema_version}
        return sha256(json.dumps(payload,sort_keys=True,separators=(",",":"),default=str).encode()).hexdigest()

class TransactionFeatureExtractor:
    NUMERIC_KEYS=("amount","hour_sin","hour_cos","weekday","is_weekend","days_since_epoch","amount_log1p")
    CATEGORICAL_KEYS=("currency","status","channel","country","payment_method","category")
    def extract(self, observation: Observation) -> FeatureVector:
        stamp=observation.occurred_at; hour=stamp.hour+stamp.minute/60
        import math
        numeric={"amount":float(observation.amount),"hour_sin":math.sin(2*math.pi*hour/24),"hour_cos":math.cos(2*math.pi*hour/24),"weekday":float(stamp.weekday()),"is_weekend":float(stamp.weekday()>=5),"days_since_epoch":(stamp-date_epoch()).total_seconds()/86400,"amount_log1p":log1p(float(observation.amount))}
        categorical={key:str(observation.attributes.get(key,"unknown")).strip().lower() for key in self.CATEGORICAL_KEYS if key!="currency"}
        categorical["currency"]=observation.currency
        return FeatureVector(observation.observation_id,observation.merchant_id,stamp,numeric,categorical)
    def batch(self, observations: Iterable[Observation]) -> list[FeatureVector]:
        return [self.extract(item) for item in observations]

def date_epoch() -> datetime:
    return datetime(1970,1,1,tzinfo=timezone.utc)

class StandardScaler:
    def __init__(self) -> None: self.means: dict[str,float]={}; self.scales: dict[str,float]={}; self.fitted=False
    def fit(self, rows: Sequence[Mapping[str,float]]) -> "StandardScaler":
        if not rows: raise ValueError("training rows required")
        keys=set(rows[0])
        if any(set(row)!=keys for row in rows): raise ValueError("feature schemas must match")
        from .statistics import mean, standard_deviation
        self.means={key:mean([float(row[key]) for row in rows]) for key in keys}
        self.scales={key:standard_deviation([float(row[key]) for row in rows],sample=False) or 1.0 for key in keys}
        self.fitted=True; return self
    def transform_one(self,row: Mapping[str,float]) -> dict[str,float]:
        if not self.fitted: raise RuntimeError("scaler is not fitted")
        if set(row)!=set(self.means): raise ValueError("feature schema mismatch")
        return {key:(float(value)-self.means[key])/self.scales[key] for key,value in row.items()}
    def transform(self,rows: Sequence[Mapping[str,float]]) -> list[dict[str,float]]:
        return [self.transform_one(row) for row in rows]
    def inverse_one(self,row: Mapping[str,float]) -> dict[str,float]:
        if not self.fitted: raise RuntimeError("scaler is not fitted")
        return {key:float(value)*self.scales[key]+self.means[key] for key,value in row.items()}

class RobustScaler:
    def __init__(self) -> None: self.centers={}; self.scales={}; self.fitted=False
    def fit(self,rows: Sequence[Mapping[str,float]]) -> "RobustScaler":
        if not rows: raise ValueError("training rows required")
        from statistics import median
        from .statistics import median_absolute_deviation
        keys=set(rows[0])
        if any(set(row)!=keys for row in rows): raise ValueError("feature schemas must match")
        self.centers={k:float(median([float(r[k]) for r in rows])) for k in keys}
        self.scales={k:median_absolute_deviation([float(r[k]) for r in rows]) or 1.0 for k in keys}
        self.fitted=True; return self
    def transform_one(self,row: Mapping[str,float]) -> dict[str,float]:
        if not self.fitted: raise RuntimeError("scaler is not fitted")
        if set(row)!=set(self.centers): raise ValueError("feature schema mismatch")
        return {k:(float(v)-self.centers[k])/self.scales[k] for k,v in row.items()}
