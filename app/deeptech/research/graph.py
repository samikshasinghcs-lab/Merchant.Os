"""Transaction relationship graph algorithms with deterministic traversal."""
from __future__ import annotations
from collections import defaultdict, deque
from dataclasses import dataclass
from typing import Hashable, Iterable, Mapping

@dataclass(frozen=True, slots=True)
class Edge:
    source: str
    target: str
    relation: str
    weight: float = 1.0
    evidence_id: str = ""
    def __post_init__(self) -> None:
        if not self.source or not self.target or not self.relation: raise ValueError("edge endpoints and relation are required")
        if self.weight<0 or not __import__("math").isfinite(self.weight): raise ValueError("edge weight must be finite and non-negative")

class RelationshipGraph:
    def __init__(self) -> None: self.nodes:set[str]=set(); self.edges:list[Edge]=[]; self._out=defaultdict(list); self._in=defaultdict(list)
    def add_node(self,node: str) -> None:
        if not node: raise ValueError("node identifier required")
        self.nodes.add(str(node))
    def add_edge(self,edge: Edge) -> None:
        self.add_node(edge.source); self.add_node(edge.target); self.edges.append(edge)
        self._out[edge.source].append(edge); self._in[edge.target].append(edge)
    def neighbors(self,node: str,relation: str|None=None) -> tuple[str,...]:
        return tuple(sorted({e.target for e in self._out.get(node,()) if relation is None or e.relation==relation}))
    def degree(self,node: str) -> int: return len(self._out.get(node,()))+len(self._in.get(node,()))
    def weighted_degree(self,node: str) -> float: return sum(e.weight for e in self._out.get(node,()))+sum(e.weight for e in self._in.get(node,()))
    def breadth_first(self,start: str,max_depth: int=3) -> tuple[str,...]:
        if start not in self.nodes: return ()
        if max_depth<0: raise ValueError("max_depth cannot be negative")
        seen={start}; queue=deque([(start,0)]); order=[]
        while queue:
            node,depth=queue.popleft(); order.append(node)
            if depth==max_depth: continue
            for neighbor in self.neighbors(node):
                if neighbor not in seen: seen.add(neighbor); queue.append((neighbor,depth+1))
        return tuple(order)
    def connected_components(self) -> tuple[tuple[str,...],...]:
        remaining=set(self.nodes); groups=[]
        while remaining:
            start=min(remaining); visited=set(self.breadth_first_undirected(start)); remaining-=visited; groups.append(tuple(sorted(visited)))
        return tuple(sorted(groups))
    def breadth_first_undirected(self,start: str) -> tuple[str,...]:
        seen={start}; queue=deque([start])
        while queue:
            node=queue.popleft()
            neighbors={e.target for e in self._out.get(node,())}|{e.source for e in self._in.get(node,())}
            for other in sorted(neighbors-seen): seen.add(other); queue.append(other)
        return tuple(sorted(seen))
    def shortest_path(self,source: str,target: str) -> tuple[str,...]|None:
        if source not in self.nodes or target not in self.nodes: return None
        queue=deque([source]); parent={source:None}
        while queue:
            node=queue.popleft()
            if node==target: break
            for nxt in self.neighbors(node):
                if nxt not in parent: parent[nxt]=node; queue.append(nxt)
        if target not in parent: return None
        path=[]; node=target
        while node is not None: path.append(node); node=parent[node]
        return tuple(reversed(path))
    def pagerank(self,damping: float=.85,iterations: int=50) -> Mapping[str,float]:
        if not 0<damping<1 or iterations<1: raise ValueError("invalid PageRank parameters")
        if not self.nodes: return {}
        nodes=sorted(self.nodes); n=len(nodes); score={node:1/n for node in nodes}
        for _ in range(iterations):
            updated={node:(1-damping)/n for node in nodes}; dangling=sum(score[node] for node in nodes if not self._out.get(node))
            for node in nodes:
                outgoing=self._out.get(node,())
                if outgoing:
                    total=sum(e.weight for e in outgoing)
                    if total==0: dangling+=score[node]
                    else:
                        for edge in outgoing: updated[edge.target]+=damping*score[node]*edge.weight/total
            share=damping*dangling/n
            score={node:updated[node]+share for node in nodes}
        return score
    def edge_density(self) -> float:
        n=len(self.nodes); return 0.0 if n<2 else len(self.edges)/(n*(n-1))
    def snapshot(self) -> dict:
        return {"nodes":sorted(self.nodes),"edges":[{"source":e.source,"target":e.target,"relation":e.relation,"weight":e.weight,"evidence_id":e.evidence_id} for e in sorted(self.edges,key=lambda x:(x.source,x.target,x.relation,x.evidence_id))]}

class GraphBuilder:
    """Builds an evidence graph from records without merging identifiers across tenants."""
    def __init__(self,tenant_id: str) -> None:
        if not tenant_id: raise ValueError("tenant_id required")
        self.tenant_id=tenant_id; self.graph=RelationshipGraph()
    def scoped(self,kind: str,identifier: str) -> str:
        if not kind or not identifier: raise ValueError("kind and identifier required")
        return f"{self.tenant_id}:{kind}:{identifier}"
    def relate(self,left_kind: str,left_id: str,right_kind: str,right_id: str,relation: str,weight: float=1.0,evidence_id: str="") -> Edge:
        edge=Edge(self.scoped(left_kind,left_id),self.scoped(right_kind,right_id),relation,weight,evidence_id)
        self.graph.add_edge(edge); return edge
