"""Deterministic k-means for exploratory merchant segmentation."""
from __future__ import annotations
from dataclasses import dataclass
from random import Random
from typing import Sequence

@dataclass(frozen=True, slots=True)
class KMeansResult:
    assignments: tuple[int,...]
    centroids: tuple[tuple[float,...],...]
    inertia: float
    iterations: int
    converged: bool

class KMeans:
    def fit(self,rows: Sequence[Sequence[float]],clusters: int,seed: int=1,max_iterations: int=100,tolerance: float=1e-6) -> KMeansResult:
        data=[tuple(map(float,row)) for row in rows]
        if not data or clusters<1 or clusters>len(data) or max_iterations<1: raise ValueError("invalid clustering input")
        width=len(data[0])
        if width==0 or any(len(row)!=width for row in data): raise ValueError("consistent non-empty vectors required")
        rng=Random(seed); centroids=[data[i] for i in rng.sample(range(len(data)),clusters)]; assignments=[-1]*len(data); converged=False
        for iteration in range(1,max_iterations+1):
            new_assignments=[]
            for row in data:
                new_assignments.append(min(range(clusters),key=lambda k:(sum((a-b)**2 for a,b in zip(row,centroids[k])),k)))
            updated=[]
            for cluster in range(clusters):
                members=[row for row,label in zip(data,new_assignments) if label==cluster]
                if not members: updated.append(centroids[cluster]); continue
                updated.append(tuple(sum(row[j] for row in members)/len(members) for j in range(width)))
            movement=max(sum((a-b)**2 for a,b in zip(old,new))**.5 for old,new in zip(centroids,updated))
            centroids=updated
            if new_assignments==assignments or movement<=tolerance: assignments=new_assignments; converged=True; break
            assignments=new_assignments
        inertia=sum(sum((a-b)**2 for a,b in zip(row,centroids[label])) for row,label in zip(data,assignments))
        return KMeansResult(tuple(assignments),tuple(centroids),inertia,iteration,converged)
