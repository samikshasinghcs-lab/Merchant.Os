"""Causal-analysis utilities that explicitly separate association from causation."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Iterable, Mapping, Sequence
from .statistics import mean, variance, covariance, correlation

@dataclass(frozen=True, slots=True)
class Association:
    treatment: str
    outcome: str
    correlation: float
    sample_size: int
    interpretation: str = "observational association; not causal evidence"

@dataclass(frozen=True, slots=True)
class EffectEstimate:
    treatment: str
    outcome: str
    treated_mean: float
    control_mean: float
    difference: float
    standard_error: float
    confidence_interval_95: tuple[float,float]
    method: str
    assumptions: tuple[str,...]

class CausalAnalyzer:
    def association(self,treatment: str,outcome: str,x: Iterable[float],y: Iterable[float]) -> Association:
        left=list(map(float,x)); right=list(map(float,y))
        if len(left)!=len(right) or len(left)<3: raise ValueError("paired samples of size >= 3 required")
        return Association(treatment,outcome,correlation(left,right),len(left))
    def difference_in_means(self,treatment: str,outcome: str,treated: Sequence[float],control: Sequence[float]) -> EffectEstimate:
        a=list(map(float,treated)); b=list(map(float,control))
        if len(a)<2 or len(b)<2: raise ValueError("each group needs at least two observations")
        delta=mean(a)-mean(b); se=(variance(a)/len(a)+variance(b)/len(b))**.5
        return EffectEstimate(treatment,outcome,mean(a),mean(b),delta,se,(delta-1.96*se,delta+1.96*se),"unadjusted difference in means",("groups are exchangeable conditional on design","no interference between units","consistent treatment definition"))
    def stratified_difference(self,treatment: str,outcome: str,treated: Sequence[tuple[str,float]],control: Sequence[tuple[str,float]]) -> EffectEstimate:
        strata=sorted({key for key,_ in treated}&{key for key,_ in control})
        if not strata: raise ValueError("no common strata")
        tmap={s:[v for k,v in treated if k==s] for s in strata}; cmap={s:[v for k,v in control if k==s] for s in strata}
        usable=[s for s in strata if tmap[s] and cmap[s]]
        if not usable: raise ValueError("no populated common strata")
        total=sum(len(tmap[s])+len(cmap[s]) for s in usable)
        weights={s:(len(tmap[s])+len(cmap[s]))/total for s in usable}
        differences={s:mean(tmap[s])-mean(cmap[s]) for s in usable}
        delta=sum(weights[s]*differences[s] for s in usable)
        se2=sum(weights[s]**2*(variance(tmap[s])/len(tmap[s])+variance(cmap[s])/len(cmap[s])) for s in usable if len(tmap[s])>1 and len(cmap[s])>1)
        se=se2**.5
        return EffectEstimate(treatment,outcome,mean([v for _,v in treated]),mean([v for _,v in control]),delta,se,(delta-1.96*se,delta+1.96*se),"stratum-weighted difference in means",("no unmeasured confounding within strata","overlap within each included stratum","no interference"))

class DirectedAcyclicGraph:
    def __init__(self,edges: Iterable[tuple[str,str]]=()) -> None:
        self.parents:dict[str,set[str]]={}; self.children:dict[str,set[str]]={}
        for left,right in edges: self.add_edge(left,right)
    def add_edge(self,parent: str,child: str) -> None:
        if not parent or not child or parent==child: raise ValueError("invalid causal edge")
        self.parents.setdefault(child,set()).add(parent); self.children.setdefault(parent,set()).add(child)
        self.parents.setdefault(parent,set()); self.children.setdefault(child,set())
        if not self.is_acyclic():
            self.parents[child].remove(parent); self.children[parent].remove(child); raise ValueError("edge creates a cycle")
    def is_acyclic(self) -> bool:
        indegree={n:len(p) for n,p in self.parents.items()}; ready=sorted(n for n,d in indegree.items() if d==0); visited=0
        while ready:
            node=ready.pop(0); visited+=1
            for child in sorted(self.children.get(node,())):
                indegree[child]-=1
                if indegree[child]==0: ready.append(child); ready.sort()
        return visited==len(indegree)
    def ancestors(self,node: str) -> tuple[str,...]:
        found=set(); stack=list(self.parents.get(node,()))
        while stack:
            item=stack.pop()
            if item not in found: found.add(item); stack.extend(self.parents.get(item,()))
        return tuple(sorted(found))
    def descendants(self,node: str) -> tuple[str,...]:
        found=set(); stack=list(self.children.get(node,()))
        while stack:
            item=stack.pop()
            if item not in found: found.add(item); stack.extend(self.children.get(item,()))
        return tuple(sorted(found))
    def backdoor_candidates(self,treatment: str) -> tuple[str,...]:
        return tuple(sorted(self.parents.get(treatment,())))
