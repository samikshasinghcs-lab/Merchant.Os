"""Nearest-neighbour propensity matching diagnostics for observational studies."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Sequence

@dataclass(frozen=True, slots=True)
class Match:
    treated_index: int
    control_index: int
    distance: float
    treated_outcome: float
    control_outcome: float
    effect: float

@dataclass(frozen=True, slots=True)
class MatchingResult:
    matches: tuple[Match,...]
    average_treatment_effect_on_treated: float
    unmatched_treated: tuple[int,...]
    caliper: float
    replacement: bool

class PropensityMatcher:
    def match(self,treatment: Sequence[int],outcomes: Sequence[float],propensity: Sequence[float],caliper: float=.1,replacement: bool=False) -> MatchingResult:
        t=list(map(int,treatment)); y=list(map(float,outcomes)); p=list(map(float,propensity))
        if not t or len(t)!=len(y) or len(t)!=len(p) or any(v not in (0,1) for v in t): raise ValueError("invalid matching arrays")
        if any(not 0<=v<=1 for v in p) or caliper<0: raise ValueError("invalid propensity or caliper")
        treated=[i for i,v in enumerate(t) if v==1]; controls=[i for i,v in enumerate(t) if v==0]; used=set(); matches=[]; unmatched=[]
        for index in treated:
            candidates=[j for j in controls if replacement or j not in used]
            if not candidates: unmatched.append(index); continue
            candidate=min(candidates,key=lambda j:(abs(p[index]-p[j]),j)); distance=abs(p[index]-p[candidate])
            if distance>caliper: unmatched.append(index); continue
            if not replacement: used.add(candidate)
            matches.append(Match(index,candidate,distance,y[index],y[candidate],y[index]-y[candidate]))
        effect=sum(m.effect for m in matches)/len(matches) if matches else 0.0
        return MatchingResult(tuple(matches),effect,tuple(unmatched),caliper,replacement)
    def balance_table(self,features: Sequence[Sequence[float]],treatment: Sequence[int]) -> dict:
        if len(features)!=len(treatment) or not features: raise ValueError("feature rows and treatment required")
        width=len(features[0])
        if any(len(row)!=width for row in features): raise ValueError("feature width mismatch")
        result={}
        for column in range(width):
            treated=[float(row[column]) for row,t in zip(features,treatment) if t==1]; control=[float(row[column]) for row,t in zip(features,treatment) if t==0]
            if not treated or not control: raise ValueError("both treatment groups required")
            mt=sum(treated)/len(treated); mc=sum(control)/len(control)
            pooled=(((sum((x-mt)**2 for x in treated)+sum((x-mc)**2 for x in control))/max(1,len(treated)+len(control)-2))**.5)
            result[str(column)]={"treated_mean":mt,"control_mean":mc,"standardized_mean_difference":(mt-mc)/pooled if pooled else 0.0}
        return result
