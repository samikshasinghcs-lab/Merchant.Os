"""Counterfactual scenario comparisons with explicit assumptions."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Callable, Mapping, Sequence

@dataclass(frozen=True, slots=True)
class CounterfactualResult:
    baseline_outcome: float
    intervention_outcome: float
    estimated_difference: float
    relative_change: float|None
    assumptions: tuple[str,...]
    uncertainty: tuple[float,float]|None=None

class CounterfactualEngine:
    def compare(self,baseline: Callable[[],float],intervention: Callable[[],float],assumptions: Sequence[str],uncertainty: tuple[float,float]|None=None) -> CounterfactualResult:
        if not assumptions: raise ValueError("assumptions must be documented")
        base=float(baseline()); changed=float(intervention())
        if not __import__("math").isfinite(base+changed): raise ValueError("outcomes must be finite")
        if uncertainty and (uncertainty[0]>uncertainty[1]): raise ValueError("invalid uncertainty interval")
        return CounterfactualResult(base,changed,changed-base,None if base==0 else (changed-base)/abs(base),tuple(assumptions),uncertainty)
    def apply_shock(self,values: Mapping[str,float],shocks: Mapping[str,float]) -> dict[str,float]:
        unknown=set(shocks)-set(values)
        if unknown: raise ValueError(f"unknown shock dimensions: {sorted(unknown)}")
        result={key:float(value) for key,value in values.items()}
        for key,shock in shocks.items():
            if not __import__("math").isfinite(float(shock)): raise ValueError("shock must be finite")
            result[key]*=(1+float(shock))
        return result
    def tornado(self,base: float,scenarios: Mapping[str,tuple[float,float]]) -> tuple[dict,...]:
        rows=[]
        for name,(low,high) in scenarios.items():
            rows.append({"driver":name,"low_delta":float(low)-base,"high_delta":float(high)-base,"span":abs(float(high)-float(low))})
        return tuple(sorted(rows,key=lambda row:(-row["span"],row["driver"])))
