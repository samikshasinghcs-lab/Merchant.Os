"""Simple cumulative-sum and mean-shift changepoint diagnostics."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Iterable
from .statistics import mean, standard_deviation

@dataclass(frozen=True, slots=True)
class ChangePoint:
    index: int
    before_mean: float
    after_mean: float
    absolute_shift: float
    standardized_shift: float

class ChangePointDetector:
    def largest_mean_shift(self,values: Iterable[float],minimum_segment: int=5) -> ChangePoint|None:
        data=list(map(float,values))
        if minimum_segment<2 or len(data)<minimum_segment*2: raise ValueError("insufficient data for segments")
        best=None
        for index in range(minimum_segment,len(data)-minimum_segment+1):
            left=data[:index]; right=data[index:]; delta=mean(right)-mean(left)
            pooled=(standard_deviation(left,False)**2/len(left)+standard_deviation(right,False)**2/len(right))**.5
            score=abs(delta)/(pooled or 1.0)
            candidate=ChangePoint(index,mean(left),mean(right),abs(delta),score)
            if best is None or candidate.standardized_shift>best.standardized_shift: best=candidate
        return best
    def cusum_path(self,values: Iterable[float],target: float,allowance: float=0.5) -> tuple[float,...]:
        if allowance<0: raise ValueError("allowance cannot be negative")
        positive=negative=0.0; output=[]
        for value in values:
            delta=float(value)-target; positive=max(0,positive+delta-allowance); negative=min(0,negative+delta+allowance); output.append(max(positive,abs(negative)))
        return tuple(output)
