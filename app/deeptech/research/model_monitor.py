"""Model monitoring for score distributions and outcome performance."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Iterable, Mapping
from .statistics import mean, standard_deviation

@dataclass(frozen=True, slots=True)
class ModelMonitorReport:
    model_name: str
    sample_size: int
    mean_score: float
    score_stddev: float
    positive_rate: float|None
    brier_score: float|None
    alerts: tuple[str,...]

class ModelMonitor:
    def evaluate(self,model_name: str,scores: Iterable[float],labels: Iterable[int]|None=None,mean_bounds: tuple[float,float]=(.05,.95)) -> ModelMonitorReport:
        values=list(map(float,scores))
        if not model_name or not values or any(not 0<=x<=1 for x in values): raise ValueError("valid model and probability scores required")
        alerts=[]; center=mean(values); spread=standard_deviation(values,False)
        if not mean_bounds[0]<=center<=mean_bounds[1]: alerts.append("SCORE_MEAN_OUTSIDE_EXPECTED_RANGE")
        if spread<.01: alerts.append("LOW_SCORE_VARIANCE")
        positive=None; brier=None
        if labels is not None:
            y=list(map(int,labels))
            if len(y)!=len(values) or any(v not in (0,1) for v in y): raise ValueError("labels must be paired binary values")
            positive=sum(y)/len(y); brier=sum((a-b)**2 for a,b in zip(y,values))/len(y)
            if brier>.25: alerts.append("BRIER_SCORE_HIGH")
        return ModelMonitorReport(model_name,len(values),center,spread,positive,brier,tuple(alerts))
