"""Transparent anomaly detectors designed for low-data merchant environments."""
from __future__ import annotations
from dataclasses import dataclass
from math import exp, log
from typing import Iterable, Mapping, Sequence
from .statistics import robust_z_score, quantile, mean, standard_deviation
from .types import Finding

@dataclass(frozen=True, slots=True)
class Threshold:
    feature: str
    lower: float | None = None
    upper: float | None = None
    severity: str = "medium"
    def evaluate(self,value: float) -> bool:
        return (self.lower is not None and value<self.lower) or (self.upper is not None and value>self.upper)

class RobustBaseline:
    def __init__(self, minimum_samples: int=20) -> None:
        if minimum_samples<3: raise ValueError("minimum_samples must be >= 3")
        self.minimum_samples=minimum_samples; self._samples: dict[str,list[float]]={}
    def fit(self, rows: Iterable[Mapping[str,float]]) -> "RobustBaseline":
        staged: dict[str,list[float]]={}
        for row in rows:
            for key,value in row.items(): staged.setdefault(key,[]).append(float(value))
        if not staged: raise ValueError("baseline rows required")
        if any(len(v)<self.minimum_samples for v in staged.values()): raise ValueError("insufficient baseline samples")
        self._samples=staged; return self
    def score(self,row: Mapping[str,float], threshold: float=3.5) -> list[Finding]:
        if not self._samples: raise RuntimeError("baseline is not fitted")
        findings=[]
        for key,value in row.items():
            if key not in self._samples: continue
            z=abs(robust_z_score(self._samples[key],float(value)))
            if z>=threshold:
                score=1-exp(-max(0,z-threshold+1)/3)
                findings.append(Finding("ROBUST_DEVIATION",min(1,score),"high" if z>=6 else "medium",f"{key} deviates from its robust baseline",{"feature":key,"robust_z":z,"baseline_median":quantile(self._samples[key],.5),"threshold":threshold}))
        return findings

class StreamingMoments:
    """Welford online moments; mergeable across disjoint partitions."""
    def __init__(self) -> None: self.count=0; self.average=0.0; self.m2=0.0; self.minimum=float("inf"); self.maximum=float("-inf")
    def update(self,value: float) -> None:
        x=float(value)
        if not __import__("math").isfinite(x): raise ValueError("value must be finite")
        self.count+=1; delta=x-self.average; self.average+=delta/self.count; self.m2+=delta*(x-self.average)
        self.minimum=min(self.minimum,x); self.maximum=max(self.maximum,x)
    @property
    def variance(self) -> float: return self.m2/(self.count-1) if self.count>1 else 0.0
    @property
    def stddev(self) -> float: return self.variance**.5
    def merge(self,other: "StreamingMoments") -> "StreamingMoments":
        if other.count==0: return self
        if self.count==0:
            self.count,self.average,self.m2,self.minimum,self.maximum=other.count,other.average,other.m2,other.minimum,other.maximum; return self
        total=self.count+other.count; delta=other.average-self.average
        self.m2+=other.m2+delta*delta*self.count*other.count/total
        self.average+=delta*other.count/total; self.count=total
        self.minimum=min(self.minimum,other.minimum); self.maximum=max(self.maximum,other.maximum)
        return self

class CUSUMDetector:
    def __init__(self, drift: float=.5, threshold: float=5.0) -> None:
        if drift<0 or threshold<=0: raise ValueError("invalid CUSUM parameters")
        self.drift=drift; self.threshold=threshold; self.positive=0.0; self.negative=0.0; self.events=0
    def update(self,value: float, target: float, scale: float) -> Finding | None:
        if scale<=0: raise ValueError("scale must be positive")
        z=(float(value)-float(target))/float(scale)
        self.positive=max(0.0,self.positive+z-self.drift); self.negative=min(0.0,self.negative+z+self.drift); self.events+=1
        magnitude=max(self.positive,abs(self.negative))
        if magnitude<self.threshold: return None
        return Finding("CUSUM_SHIFT",min(1.0,1-exp(-magnitude/self.threshold)),"high","sequential change detector crossed its threshold",{"positive_sum":self.positive,"negative_sum":self.negative,"events_seen":self.events,"normalized_observation":z})
    def reset(self) -> None: self.positive=0.0; self.negative=0.0; self.events=0

class IsolationScore:
    """Small-data distance-to-centroid detector; not a substitute for Isolation Forest."""
    def __init__(self) -> None: self.center={}; self.spread={}; self.fitted=False
    def fit(self,rows: Sequence[Mapping[str,float]]) -> "IsolationScore":
        if len(rows)<5: raise ValueError("at least five rows required")
        keys=set(rows[0])
        if any(set(r)!=keys for r in rows): raise ValueError("feature schema mismatch")
        self.center={k:mean([float(r[k]) for r in rows]) for k in keys}
        self.spread={k:standard_deviation([float(r[k]) for r in rows],False) or 1.0 for k in keys}
        self.fitted=True; return self
    def score_one(self,row: Mapping[str,float]) -> float:
        if not self.fitted: raise RuntimeError("detector is not fitted")
        if set(row)!=set(self.center): raise ValueError("feature schema mismatch")
        distance=sum(((float(row[k])-self.center[k])/self.spread[k])**2 for k in self.center)**.5
        return 1-exp(-distance/max(1,len(self.center)**.5))
