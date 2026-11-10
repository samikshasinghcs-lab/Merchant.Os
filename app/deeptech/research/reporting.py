"""Deterministic aggregation helpers for merchant intelligence reporting."""
from __future__ import annotations
from collections import defaultdict
from decimal import Decimal
from typing import Iterable, Mapping
from .money import decimal_value

class Aggregator:
    def sum_by(self,rows: Iterable[Mapping],group_field: str,value_field: str) -> Mapping[str,Decimal]:
        totals=defaultdict(Decimal)
        for row in rows:
            if group_field not in row or value_field not in row: raise ValueError("aggregation field missing")
            totals[str(row[group_field])]+=decimal_value(row[value_field])
        return {key:totals[key] for key in sorted(totals)}
    def count_by(self,rows: Iterable[Mapping],group_field: str) -> Mapping[str,int]:
        totals=defaultdict(int)
        for row in rows:
            if group_field not in row: raise ValueError("group field missing")
            totals[str(row[group_field])]+=1
        return {key:totals[key] for key in sorted(totals)}
    def rate_by(self,rows: Iterable[Mapping],group_field: str,numerator_field: str,denominator_field: str) -> Mapping[str,float|None]:
        sums=defaultdict(lambda:[0.0,0.0])
        for row in rows:
            key=str(row[group_field]); sums[key][0]+=float(row[numerator_field]); sums[key][1]+=float(row[denominator_field])
        return {key:(values[0]/values[1] if values[1] else None) for key,values in sorted(sums.items())}
    def top_n(self,values: Mapping[str,float],n: int=10) -> tuple[tuple[str,float],...]:
        if n<1: raise ValueError("n must be positive")
        return tuple(sorted(((key,float(value)) for key,value in values.items()),key=lambda x:(-x[1],x[0]))[:n])
