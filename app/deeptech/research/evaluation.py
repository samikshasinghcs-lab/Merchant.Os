"""Binary classifier evaluation and calibration diagnostics."""
from __future__ import annotations
from dataclasses import dataclass
from math import log
from typing import Iterable, Sequence
from .statistics import mean

@dataclass(frozen=True, slots=True)
class ClassificationMetrics:
    true_positive: int
    false_positive: int
    true_negative: int
    false_negative: int
    precision: float
    recall: float
    specificity: float
    f1: float
    accuracy: float
    balanced_accuracy: float

class Evaluator:
    def classification(self,labels: Iterable[int],probabilities: Iterable[float],threshold: float=.5) -> ClassificationMetrics:
        y=list(map(int,labels)); p=list(map(float,probabilities))
        if not y or len(y)!=len(p) or any(v not in (0,1) for v in y): raise ValueError("binary labels and equal predictions required")
        if any(not 0<=v<=1 for v in p) or not 0<=threshold<=1: raise ValueError("probabilities and threshold must be in [0,1]")
        tp=sum(a==1 and b>=threshold for a,b in zip(y,p)); fp=sum(a==0 and b>=threshold for a,b in zip(y,p)); tn=sum(a==0 and b<threshold for a,b in zip(y,p)); fn=sum(a==1 and b<threshold for a,b in zip(y,p))
        precision=tp/(tp+fp) if tp+fp else 0.0; recall=tp/(tp+fn) if tp+fn else 0.0; specificity=tn/(tn+fp) if tn+fp else 0.0
        f1=2*precision*recall/(precision+recall) if precision+recall else 0.0; accuracy=(tp+tn)/len(y); balanced=(recall+specificity)/2
        return ClassificationMetrics(tp,fp,tn,fn,precision,recall,specificity,f1,accuracy,balanced)
    def brier_score(self,labels: Iterable[int],probabilities: Iterable[float]) -> float:
        y=list(map(int,labels)); p=list(map(float,probabilities))
        if not y or len(y)!=len(p) or any(v not in (0,1) for v in y) or any(not 0<=v<=1 for v in p): raise ValueError("invalid labels or probabilities")
        return mean([(a-b)**2 for a,b in zip(y,p)])
    def log_loss(self,labels: Iterable[int],probabilities: Iterable[float],epsilon: float=1e-15) -> float:
        y=list(map(int,labels)); p=list(map(float,probabilities))
        if not y or len(y)!=len(p) or any(v not in (0,1) for v in y): raise ValueError("invalid labels")
        if any(not 0<=v<=1 for v in p): raise ValueError("probabilities must be in [0,1]")
        return -mean([a*log(max(epsilon,b))+(1-a)*log(max(epsilon,1-b)) for a,b in zip(y,p)])
    def calibration_bins(self,labels: Sequence[int],probabilities: Sequence[float],bins: int=10) -> tuple[dict,...]:
        if len(labels)!=len(probabilities) or not labels or bins<2: raise ValueError("invalid calibration input")
        result=[]
        for index in range(bins):
            lo=index/bins; hi=(index+1)/bins
            pairs=[(int(y),float(p)) for y,p in zip(labels,probabilities) if lo<=p<(hi if index<bins-1 else hi+1e-12)]
            if pairs: result.append({"lower":lo,"upper":hi,"count":len(pairs),"mean_prediction":mean([p for _,p in pairs]),"observed_rate":mean([y for y,_ in pairs])})
        return tuple(result)
    def expected_calibration_error(self,labels: Sequence[int],probabilities: Sequence[float],bins: int=10) -> float:
        groups=self.calibration_bins(labels,probabilities,bins); total=len(labels)
        return sum(group["count"]/total*abs(group["mean_prediction"]-group["observed_rate"]) for group in groups)
