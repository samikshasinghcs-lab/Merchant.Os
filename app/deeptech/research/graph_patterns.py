"""Graph pattern queries for shared-entity and multi-hop investigation."""
from __future__ import annotations
from typing import Iterable
from .graph import RelationshipGraph

class GraphPatternQuery:
    def shared_neighbors(self,graph: RelationshipGraph,left: str,right: str) -> tuple[str,...]:
        return tuple(sorted(set(graph.neighbors(left))&set(graph.neighbors(right))))
    def two_hop_paths(self,graph: RelationshipGraph,source: str,target: str) -> tuple[tuple[str,str,str],...]:
        paths=[]
        for middle in graph.neighbors(source):
            if target in graph.neighbors(middle): paths.append((source,middle,target))
        return tuple(paths)
    def entities_connected_to_many(self,graph: RelationshipGraph,targets: Iterable[str],minimum: int=2) -> tuple[tuple[str,int],...]:
        if minimum<1: raise ValueError("minimum must be positive")
        target_set=set(targets); counts={}
        for node in graph.nodes:
            neighbors=set(graph.neighbors(node)); count=len(neighbors&target_set)
            if count>=minimum: counts[node]=count
        return tuple(sorted(counts.items(),key=lambda item:(-item[1],item[0])))
    def path_evidence(self,graph: RelationshipGraph,path: Iterable[str]) -> tuple[dict,...]:
        nodes=tuple(path); result=[]
        for left,right in zip(nodes,nodes[1:]):
            edges=[edge for edge in graph._out.get(left,()) if edge.target==right]
            result.extend({"source":edge.source,"target":edge.target,"relation":edge.relation,"weight":edge.weight,"evidence_id":edge.evidence_id} for edge in edges)
        return tuple(result)
