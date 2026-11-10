"""Connected-component and label-propagation community heuristics."""
from __future__ import annotations
from collections import Counter
from typing import Mapping
from .graph import RelationshipGraph

class CommunityDetector:
    def label_propagation(self,graph: RelationshipGraph,iterations: int=20) -> Mapping[str,int]:
        if iterations<1: raise ValueError("iterations must be positive")
        labels={node:index for index,node in enumerate(sorted(graph.nodes))}
        for _ in range(iterations):
            changed=False
            for node in sorted(graph.nodes):
                neighbors=set(graph.neighbors(node))|{edge.source for edge in graph._in.get(node,())}
                if not neighbors: continue
                counts=Counter(labels[item] for item in neighbors); maximum=max(counts.values())
                selected=min(label for label,count in counts.items() if count==maximum)
                if selected!=labels[node]: labels[node]=selected; changed=True
            if not changed: break
        remap={label:index for index,label in enumerate(sorted(set(labels.values())))}
        return {node:remap[label] for node,label in labels.items()}
    def modularity(self,graph: RelationshipGraph,communities: Mapping[str,int]) -> float:
        if set(communities)!=graph.nodes: raise ValueError("community assignment must cover graph nodes")
        m=len(graph.edges)
        if m==0: return 0.0
        degree={node:graph.degree(node) for node in graph.nodes}; internal=0
        for edge in graph.edges:
            if communities[edge.source]==communities[edge.target]: internal+=1
        community_degree={}
        for node,label in communities.items(): community_degree[label]=community_degree.get(label,0)+degree[node]
        expected=sum((value/(2*m))**2 for value in community_degree.values())
        return internal/m-expected
    def component_summary(self,graph: RelationshipGraph) -> tuple[dict,...]:
        return tuple({"community_id":index,"size":len(nodes),"nodes":nodes} for index,nodes in enumerate(graph.connected_components()))
