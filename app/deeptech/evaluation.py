"""Model evaluation utilities with threshold and probability-quality metrics."""
from __future__ import annotations
from dataclasses import dataclass
from math import isfinite
from typing import Iterable, Sequence

@dataclass(frozen=True, slots=True)
class BinaryMetrics:
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

def binary_metrics(y_true: Sequence[int], y_pred: Sequence[int]) -> BinaryMetrics:
    if len(y_true) != len(y_pred) or not y_true:
        raise ValueError("y_true and y_pred must have equal non-zero length")
    if any(v not in (0,1) for v in y_true) or any(v not in (0,1) for v in y_pred):
        raise ValueError("labels must be binary 0/1")
    tp=sum(a==1 and b==1 for a,b in zip(y_true,y_pred)); fp=sum(a==0 and b==1 for a,b in zip(y_true,y_pred))
    tn=sum(a==0 and b==0 for a,b in zip(y_true,y_pred)); fn=sum(a==1 and b==0 for a,b in zip(y_true,y_pred))
    precision=tp/(tp+fp) if tp+fp else 0.0; recall=tp/(tp+fn) if tp+fn else 0.0
    specificity=tn/(tn+fp) if tn+fp else 0.0; f1=2*precision*recall/(precision+recall) if precision+recall else 0.0
    accuracy=(tp+tn)/len(y_true); balanced=(recall+specificity)/2
    return BinaryMetrics(tp,fp,tn,fn,precision,recall,specificity,f1,accuracy,balanced)

def brier_score(y_true: Sequence[int], probabilities: Sequence[float]) -> float:
    if len(y_true) != len(probabilities) or not y_true:
        raise ValueError("inputs must have equal non-zero length")
    if any(v not in (0,1) for v in y_true):
        raise ValueError("labels must be binary 0/1")
    if any(not isfinite(p) or not 0 <= p <= 1 for p in probabilities):
        raise ValueError("probabilities must be finite and in [0,1]")
    return sum((p-y)**2 for y,p in zip(y_true,probabilities))/len(y_true)

def calibration_table(y_true: Sequence[int], probabilities: Sequence[float], bins: int = 10) -> list[dict[str,float|int]]:
    if bins < 2 or len(y_true) != len(probabilities) or not y_true:
        raise ValueError("invalid calibration inputs")
    if any(y not in (0,1) for y in y_true) or any(not isfinite(p) or not 0 <= p <= 1 for p in probabilities):
        raise ValueError("invalid labels or probabilities")
    result=[]
    for index in range(bins):
        low=index/bins; high=(index+1)/bins
        selected=[(y,p) for y,p in zip(y_true,probabilities) if low <= p < high or (index==bins-1 and p==1)]
        if selected:
            result.append({"bin":index,"count":len(selected),"mean_probability":sum(p for _,p in selected)/len(selected),"observed_rate":sum(y for y,_ in selected)/len(selected)})
        else:
            result.append({"bin":index,"count":0,"mean_probability":0.0,"observed_rate":0.0})
    return result

def precision_recall_curve(y_true: Sequence[int], scores: Sequence[float]) -> list[dict[str,float]]:
    if len(y_true) != len(scores) or not y_true:
        raise ValueError("inputs must have equal non-zero length")
    if any(y not in (0,1) for y in y_true) or any(not isfinite(float(s)) for s in scores):
        raise ValueError("invalid labels or scores")
    thresholds=sorted(set(float(s) for s in scores), reverse=True)
    positives=sum(y_true); curve=[]
    for threshold in thresholds:
        pred=[int(s>=threshold) for s in scores]
        metrics=binary_metrics(y_true,pred)
        curve.append({"threshold":threshold,"precision":metrics.precision,"recall":metrics.recall})
    return curve

def temporal_split(records: Sequence[dict], timestamp_key: str, test_fraction: float = .2) -> tuple[list[dict],list[dict]]:
    """Chronological split; prevents random shuffling from leaking future rows."""
    if not 0 < test_fraction < 1 or len(records) < 2:
        raise ValueError("test_fraction must be in (0,1) and at least two records are required")
    ordered=sorted(records,key=lambda row:row[timestamp_key])
    cut=max(1,min(len(ordered)-1,int(len(ordered)*(1-test_fraction))))
    return ordered[:cut],ordered[cut:]
