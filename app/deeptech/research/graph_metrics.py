"""Additional graph metrics for transaction relationship investigations."""
from __future__ import annotations
from collections import deque
from typing import Mapping
from .graph import RelationshipGraph

class GraphMetrics:
    def closeness(self,graph: RelationshipGraph,node: str) -> float:
        if node not in graph.nodes: return 0.0
        distances={node:0}; queue=deque([node])
        while queue:
            current=queue.popleft()
            for neighbor in graph.neighbors(current):
                if neighbor not in distances: distances[neighbor]=distances[current]+1; queue.append(neighbor)
        reachable=len(distances)-1
        if reachable==0: return 0.0
        return reachable/sum(distances.values())*(reachable/(len(graph.nodes)-1))
    def betweenness_approx(self,graph: RelationshipGraph) -> Mapping[str,float]:
        score={node:0.0 for node in graph.nodes}
        for source in sorted(graph.nodes):
            stack=[]; predecessors={v:[] for v in graph.nodes}; paths={v:0 for v in graph.nodes}; paths[source]=1; distance={v:-1 for v in graph.nodes}; distance[source]=0; queue=deque([source])
            while queue:
                v=queue.popleft(); stack.append(v)
                for w in graph.neighbors(v):
                    if distance[w]<0: queue.append(w); distance[w]=distance[v]+1
                    if distance[w]==distance[v]+1: paths[w]+=paths[v]; predecessors[w].append(v)
            dependency={v:0.0 for v in graph.nodes}
            while stack:
                w=stack.pop()
                for v in predecessors[w]: dependency[v]+=(paths[v]/paths[w])*(1+dependency[w]) if paths[w] else 0
                if w!=source: score[w]+=dependency[w]
        n=len(graph.nodes)
        scale=1/((n-1)*(n-2)) if n>2 else 1.0
        return {node:value*scale for node,value in score.items()}
    def clustering_coefficient(self,graph: RelationshipGraph,node: str) -> float:
        neighbors=set(graph.neighbors(node))
        for edge in graph._in.get(node,()): neighbors.add(edge.source)
        n=len(neighbors)
        if n<2: return 0.0
        links=0
        for left in neighbors:
            for right in neighbors:
                if left<right and (right in graph.neighbors(left) or left in graph.neighbors(right)): links+=1
        return 2*links/(n*(n-1))
