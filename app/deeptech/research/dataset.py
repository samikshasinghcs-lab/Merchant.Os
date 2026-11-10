"""Dataset contracts and leakage-aware splitting for model experiments."""
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime
from typing import Iterable, Mapping, Sequence

@dataclass(frozen=True, slots=True)
class DatasetContract:
    name: str
    version: str
    feature_names: tuple[str,...]
    target_name: str
    timestamp_name: str
    entity_name: str
    prohibited_features: tuple[str,...]=()
    def validate(self,rows: Sequence[Mapping[str,object]]) -> None:
        if not rows: raise ValueError("dataset cannot be empty")
        required=set(self.feature_names)|{self.target_name,self.timestamp_name,self.entity_name}
        for index,row in enumerate(rows):
            missing=required-set(row)
            if missing: raise ValueError(f"row {index} missing fields: {sorted(missing)}")
            leaked=set(self.feature_names)&set(self.prohibited_features)
            if leaked: raise ValueError(f"prohibited features: {sorted(leaked)}")
            if not isinstance(row[self.timestamp_name],datetime): raise ValueError("timestamps must be datetime values")

@dataclass(frozen=True, slots=True)
class Split:
    train: tuple[int,...]
    validation: tuple[int,...]
    test: tuple[int,...]
    def validate(self,n: int) -> None:
        combined=self.train+self.validation+self.test
        if len(set(combined))!=len(combined) or any(i<0 or i>=n for i in combined): raise ValueError("split indices overlap or are out of range")
        if len(combined)!=n: raise ValueError("split must partition every row")

def temporal_split(timestamps: Sequence[datetime],train_fraction: float=.7,validation_fraction: float=.15) -> Split:
    if not 0<train_fraction<1 or not 0<validation_fraction<1 or train_fraction+validation_fraction>=1: raise ValueError("invalid split fractions")
    if any(t.tzinfo is None for t in timestamps): raise ValueError("timestamps must be timezone-aware")
    order=sorted(range(len(timestamps)),key=lambda i:(timestamps[i],i)); n=len(order)
    a=int(n*train_fraction); b=int(n*(train_fraction+validation_fraction))
    if a<1 or b<=a or b>=n: raise ValueError("insufficient rows for three-way split")
    split=Split(tuple(order[:a]),tuple(order[a:b]),tuple(order[b:])); split.validate(n); return split

def grouped_split(groups: Sequence[str],train_fraction: float=.8) -> Split:
    if not 0<train_fraction<1 or not groups: raise ValueError("invalid grouped split")
    unique=sorted(set(groups)); cut=max(1,min(len(unique)-1,int(len(unique)*train_fraction)))
    train_groups=set(unique[:cut]); train=tuple(i for i,g in enumerate(groups) if g in train_groups); test=tuple(i for i,g in enumerate(groups) if g not in train_groups)
    return Split(train,(),test)
