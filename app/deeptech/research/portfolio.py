"""Portfolio-level concentration and exposure analytics."""
from __future__ import annotations
from math import sqrt
from typing import Mapping, Sequence

class PortfolioAnalytics:
    def concentration(self,exposures: Mapping[str,float]) -> dict:
        values={k:float(v) for k,v in exposures.items()}
        if any(v<0 for v in values.values()): raise ValueError("exposures must be non-negative")
        total=sum(values.values())
        if total==0: return {"total":0.0,"shares":{},"hhi":0.0,"effective_entities":0.0,"largest_share":0.0}
        shares={k:v/total for k,v in values.items()}; hhi=sum(x*x for x in shares.values())
        return {"total":total,"shares":shares,"hhi":hhi,"effective_entities":1/hhi,"largest_share":max(shares.values())}
    def covariance_matrix(self,series: Mapping[str,Sequence[float]]) -> dict:
        from .statistics import covariance
        names=sorted(series); result={}
        if len(names)<1: raise ValueError("series required")
        for left in names:
            result[left]={}
            for right in names: result[left][right]=covariance(series[left],series[right])
        return result
    def portfolio_volatility(self,weights: Mapping[str,float],covariances: Mapping[str,Mapping[str,float]]) -> float:
        names=sorted(weights)
        if set(names)-set(covariances): raise ValueError("missing covariance rows")
        variance=0.0
        for left in names:
            for right in names: variance+=weights[left]*weights[right]*covariances[left][right]
        if variance< -1e-10: raise ValueError("covariance matrix produced negative variance")
        return sqrt(max(0,variance))
