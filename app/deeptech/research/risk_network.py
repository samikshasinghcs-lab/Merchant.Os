"""Risk propagation over evidence graphs with bounded, explainable diffusion."""
from __future__ import annotations
from typing import Mapping
from .graph import RelationshipGraph

class RiskDiffusion:
    def propagate(self,graph: RelationshipGraph,seeds: Mapping[str,float],decay: float=.5,iterations: int=5) -> Mapping[str,float]:
        if not 0<=decay<=1 or iterations<1: raise ValueError("invalid diffusion parameters")
        if any(node not in graph.nodes for node in seeds): raise ValueError("seed node missing from graph")
        if any(not 0<=float(value)<=1 for value in seeds.values()): raise ValueError("seed risks must be in [0,1]")
        scores={node:float(seeds.get(node,0)) for node in graph.nodes}
        fixed=set(seeds)
        for _ in range(iterations):
            updated=dict(scores)
            for node in graph.nodes:
                if node in fixed: continue
                incoming=graph._in.get(node,())
                if not incoming: continue
                total=sum(edge.weight for edge in incoming)
                propagated=sum(scores[edge.source]*edge.weight for edge in incoming)/(total or 1)
                updated[node]=min(1.0,max(0.0,decay*propagated))
            scores=updated
        return scores
    def top_exposures(self,scores: Mapping[str,float],limit: int=10) -> tuple[tuple[str,float],...]:
        if limit<1: raise ValueError("limit must be positive")
        return tuple(sorted(((node,float(score)) for node,score in scores.items()),key=lambda item:(-item[1],item[0]))[:limit])
