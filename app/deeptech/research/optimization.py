"""Constrained resource allocation and sensitivity analysis."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Iterable, Sequence

@dataclass(frozen=True, slots=True)
class Allocation:
    quantities: tuple[int,...]
    objective: float
    used_budget: float
    remaining_budget: float

class KnapsackAllocator:
    """Exact 0/1 knapsack for small operational intervention portfolios."""
    def solve(self,costs: Sequence[int],values: Sequence[float],budget: int) -> Allocation:
        if len(costs)!=len(values) or not costs or budget<0: raise ValueError("invalid knapsack inputs")
        if any(int(c)<0 for c in costs) or any(float(v)<0 for v in values): raise ValueError("costs and values must be non-negative")
        n=len(costs); dp=[(0.0,()) for _ in range(budget+1)]
        for index,(cost,value) in enumerate(zip(costs,values)):
            cost=int(cost); value=float(value)
            for capacity in range(budget,cost-1,-1):
                candidate=dp[capacity-cost][0]+value
                if candidate>dp[capacity][0]: dp[capacity]=(candidate,dp[capacity-cost][1]+(index,))
        best=max((dp[c] for c in range(budget+1)),key=lambda item:item[0]); chosen=set(best[1]); quantities=tuple(1 if i in chosen else 0 for i in range(n)); used=sum(int(c)*q for c,q in zip(costs,quantities))
        return Allocation(quantities,best[0],float(used),float(budget-used))

class GreedyAllocator:
    def solve(self,costs: Sequence[float],values: Sequence[float],budget: float) -> Allocation:
        if len(costs)!=len(values) or budget<0: raise ValueError("invalid inputs")
        ranked=sorted(range(len(costs)),key=lambda i:(-(values[i]/costs[i] if costs[i]>0 else float("inf")),i))
        chosen=[]; remaining=float(budget); objective=0.0
        for i in ranked:
            if costs[i]<0 or values[i]<0: raise ValueError("costs and values must be non-negative")
            if costs[i]<=remaining: chosen.append(i); remaining-=costs[i]; objective+=values[i]
        quantities=tuple(1 if i in chosen else 0 for i in range(len(costs)))
        return Allocation(quantities,objective,budget-remaining,remaining)

def one_way_sensitivity(base: float,changes: Iterable[float],recalculate) -> tuple[dict,...]:
    rows=[]
    for change in changes:
        value=float(recalculate(float(change))); rows.append({"input_change":float(change),"output":value,"delta_from_base":value-float(base)})
    return tuple(rows)

def elasticity(base_input: float,new_input: float,base_output: float,new_output: float) -> float:
    if base_input==0 or base_output==0: raise ValueError("base values must be non-zero")
    input_change=(new_input-base_input)/abs(base_input); output_change=(new_output-base_output)/abs(base_output)
    if input_change==0: raise ValueError("input change cannot be zero")
    return output_change/input_change
