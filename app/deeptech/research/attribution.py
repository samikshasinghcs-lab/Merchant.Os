"""Deterministic contribution attribution and variance decomposition."""
from __future__ import annotations
from typing import Callable, Mapping, Sequence
from itertools import combinations

class AttributionEngine:
    def waterfall(self,start: float,changes: Mapping[str,float]) -> tuple[dict,...]:
        current=float(start); rows=[]
        for name,delta in changes.items():
            before=current; current+=float(delta)
            rows.append({"driver":name,"start":before,"change":float(delta),"end":current})
        return tuple(rows)
    def normalized_contributions(self,contributions: Mapping[str,float]) -> Mapping[str,float]:
        total=sum(abs(float(v)) for v in contributions.values())
        if total==0: return {key:0.0 for key in contributions}
        return {key:float(value)/total for key,value in contributions.items()}
    def shapley_values(self,players: Sequence[str],value_function: Callable[[frozenset[str]],float]) -> Mapping[str,float]:
        """Exact Shapley values; exponential and intended for small player counts."""
        names=tuple(players); n=len(names)
        if not names or len(set(names))!=n or n>12: raise ValueError("require 1..12 unique players")
        import math
        result={name:0.0 for name in names}; factorial=math.factorial
        for name in names:
            others=[item for item in names if item!=name]
            for size in range(n):
                weight=factorial(size)*factorial(n-size-1)/factorial(n)
                for subset in combinations(others,size):
                    coalition=frozenset(subset); result[name]+=weight*(value_function(coalition|{name})-value_function(coalition))
        return result
    def verify_efficiency(self,players: Sequence[str],values: Mapping[str,float],value_function: Callable[[frozenset[str]],float],tolerance: float=1e-8) -> bool:
        return abs(sum(values.values())-(value_function(frozenset(players))-value_function(frozenset())))<=tolerance
