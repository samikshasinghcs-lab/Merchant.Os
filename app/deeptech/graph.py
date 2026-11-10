"""In-memory transaction relationship graph for explainable investigations."""
from __future__ import annotations
from collections import defaultdict, deque
from dataclasses import dataclass
from decimal import Decimal
from typing import Iterable
from .models import Transaction

@dataclass(frozen=True, slots=True)
class GraphEdge:
    source: str
    target: str
    relation: str
    weight: float
    transaction_ids: tuple[str, ...]

class TransactionGraph:
    """Builds an attributed graph from transactions without inferring identity.

    Nodes are namespaced (merchant/customer/product/order) to avoid collisions.
    Only exact identifier equality creates a relationship. The graph is an
    investigative aid, not proof of fraud or common ownership.
    """
    def __init__(self):
        self._adj: dict[str, dict[str, float]] = defaultdict(dict)
        self._edges: list[GraphEdge] = []
        self._tx_nodes: dict[str, set[str]] = {}
        self._node_tx: dict[str, set[str]] = defaultdict(set)
        self._node_amount: dict[str, dict[str, Decimal]] = defaultdict(lambda: defaultdict(Decimal))
        self._seen_transaction_ids: set[str] = set()

    @staticmethod
    def _node(kind: str, value: str | None) -> str | None:
        return f"{kind}:{value}" if value else None

    def add_transaction(self, tx: Transaction) -> None:
        if tx.transaction_id in self._seen_transaction_ids:
            raise ValueError(f"duplicate transaction_id: {tx.transaction_id}")
        self._seen_transaction_ids.add(tx.transaction_id)
        # Non-merchant identifiers are tenant-scoped. This prevents identical
        # customer/product/channel labels in different merchants from linking.
        nodes = [self._node("merchant", tx.merchant_id),
                 self._node("customer", f"{tx.merchant_id}:{tx.customer_id}" if tx.customer_id else None),
                 self._node("product", f"{tx.merchant_id}:{tx.product_id}" if tx.product_id else None),
                 self._node("channel", f"{tx.merchant_id}:{tx.channel}" if tx.channel else None),
                 self._node("country", f"{tx.merchant_id}:{tx.country}" if tx.country else None)]
        nodes = [n for n in nodes if n]
        self._tx_nodes[tx.transaction_id] = set(nodes)
        for node in nodes:
            self._node_tx[node].add(tx.transaction_id)
            self._node_amount[node][tx.currency] += tx.amount
        for i, left in enumerate(nodes):
            for right in nodes[i + 1:]:
                self._adj[left][right] = self._adj[left].get(right, 0.0) + 1.0
                self._adj[right][left] = self._adj[right].get(left, 0.0) + 1.0
                self._edges.append(GraphEdge(left, right, "CO_OCCURS_IN_TRANSACTION", 1.0, (tx.transaction_id,)))

    @classmethod
    def from_transactions(cls, transactions: Iterable[Transaction]) -> "TransactionGraph":
        graph = cls()
        for tx in transactions:
            graph.add_transaction(tx)
        return graph

    @property
    def node_count(self) -> int:
        return len(self._node_tx)

    @property
    def edge_count(self) -> int:
        return sum(len(v) for v in self._adj.values()) // 2

    def neighbors(self, node: str) -> dict[str, float]:
        return dict(self._adj.get(node, {}))

    def transaction_ids(self, node: str) -> tuple[str, ...]:
        return tuple(sorted(self._node_tx.get(node, set())))

    def connected_components(self) -> list[tuple[str, ...]]:
        unseen = set(self._node_tx)
        components = []
        while unseen:
            start = unseen.pop(); queue = deque([start]); component = [start]
            while queue:
                current = queue.popleft()
                for neighbor in self._adj.get(current, {}):
                    if neighbor in unseen:
                        unseen.remove(neighbor); queue.append(neighbor); component.append(neighbor)
            components.append(tuple(sorted(component)))
        return sorted(components, key=lambda c: (-len(c), c))

    def degree_centrality(self) -> dict[str, float]:
        n = self.node_count
        if n <= 1:
            return {node: 0.0 for node in self._node_tx}
        return {node: len(neighbors) / (n - 1) for node, neighbors in self._adj.items()}

    def weighted_pagerank(self, damping: float = 0.85, iterations: int = 30, tolerance: float = 1e-9) -> dict[str, float]:
        if not 0 < damping < 1 or iterations < 1 or tolerance <= 0:
            raise ValueError("invalid PageRank parameters")
        nodes = sorted(self._node_tx); n = len(nodes)
        if not n:
            return {}
        rank = {node: 1.0 / n for node in nodes}
        for _ in range(iterations):
            updated = {node: (1 - damping) / n for node in nodes}
            dangling = sum(rank[node] for node in nodes if not self._adj[node])
            for node in nodes:
                updated[node] += damping * dangling / n
                total = sum(self._adj[node].values())
                if total:
                    for neighbor, weight in self._adj[node].items():
                        updated[neighbor] += damping * rank[node] * weight / total
            delta = sum(abs(updated[node] - rank[node]) for node in nodes)
            rank = updated
            if delta < tolerance:
                break
        return rank

    def node_summary(self, node: str) -> dict[str, object]:
        return {"node": node, "degree": len(self._adj.get(node, {})), "transaction_count": len(self._node_tx.get(node, set())), "gross_amount_by_currency": {currency: str(amount) for currency, amount in sorted(self._node_amount.get(node, {}).items())}, "transactions": list(self.transaction_ids(node))}

    def candidate_shared_identifiers(self, min_transactions: int = 3) -> list[dict[str, object]]:
        """Return high-frequency exact identifiers for analyst review, not risk labels."""
        if min_transactions < 2:
            raise ValueError("min_transactions must be at least 2")
        return [self.node_summary(node) for node, ids in sorted(self._node_tx.items()) if node.startswith("customer:") and len(ids) >= min_transactions]

    def export_edges(self) -> list[dict[str, object]]:
        return [{"source": e.source, "target": e.target, "relation": e.relation, "weight": e.weight, "transaction_ids": list(e.transaction_ids)} for e in self._edges]
