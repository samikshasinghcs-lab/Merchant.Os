"""Test support factories; synthetic values are never presented as merchant facts."""
from __future__ import annotations
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from random import Random
from typing import Iterable
from .types import Observation

def synthetic_observations(count: int=30,tenant_id: str="test-tenant",seed: int=7) -> list[Observation]:
    if count<1: raise ValueError("count must be positive")
    rng=Random(seed); start=datetime(2026,1,1,tzinfo=timezone.utc); rows=[]
    for index in range(count):
        rows.append(Observation(f"txn-{index}",tenant_id,start+timedelta(minutes=index*17),Decimal(str(round(rng.uniform(10,250),2))),"USD",{"customer_id":f"customer-{index%7}","channel":"web","status":"completed"}))
    return rows

def seeded_values(count: int=100,seed: int=11,center: float=0.0,spread: float=1.0) -> tuple[float,...]:
    if count<1 or spread<0: raise ValueError("invalid synthetic sample parameters")
    rng=Random(seed); return tuple(rng.gauss(center,spread) for _ in range(count))
