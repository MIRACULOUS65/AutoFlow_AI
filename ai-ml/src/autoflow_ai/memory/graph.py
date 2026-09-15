"""Simple in-memory graph memory (interface + first implementation).

Records relationships between applications, tools, actions, artifacts,
workflows and capabilities. Kept intentionally simple; the interface allows a
real graph backend later without changing callers.
"""

from __future__ import annotations

from .models import GraphEdge, GraphNode


class GraphMemory:
    def __init__(self) -> None:
        self._nodes: dict[str, GraphNode] = {}
        self._edges: list[GraphEdge] = []

    def add_node(self, node: GraphNode) -> None:
        self._nodes[node.node_id] = node

    def add_edge(self, edge: GraphEdge) -> None:
        # de-dup identical edges
        for e in self._edges:
            if (e.from_id, e.to_id, e.relation) == (edge.from_id, edge.to_id, edge.relation):
                return
        self._edges.append(edge)

    def record_workflow(self, workflow_id: str, *, tools: list[str], verifier: str | None = None,
                        artifacts: list[str] | None = None) -> None:
        self.add_node(GraphNode(node_id=workflow_id, kind="workflow", label=workflow_id))
        for tool in tools:
            self.add_node(GraphNode(node_id=f"tool:{tool}", kind="tool", label=tool))
            self.add_edge(GraphEdge(from_id=workflow_id, to_id=f"tool:{tool}", relation="USES"))
        for art in artifacts or []:
            self.add_node(GraphNode(node_id=f"artifact:{art}", kind="artifact", label=art))
            self.add_edge(GraphEdge(from_id=workflow_id, to_id=f"artifact:{art}", relation="PRODUCES"))
        if verifier:
            self.add_node(GraphNode(node_id=f"verifier:{verifier}", kind="action", label=verifier))
            self.add_edge(GraphEdge(from_id=workflow_id, to_id=f"verifier:{verifier}", relation="VERIFIED_BY"))

    def neighbors(self, node_id: str, *, relation: str | None = None) -> list[GraphEdge]:
        return [
            e
            for e in self._edges
            if e.from_id == node_id and (relation is None or e.relation == relation)
        ]

    def query(self, node_id: str) -> dict:
        return {
            "node": self._nodes.get(node_id).model_dump(mode="json") if node_id in self._nodes else None,
            "edges": [e.model_dump(mode="json") for e in self.neighbors(node_id)],
        }

    def summary(self) -> dict:
        kinds: dict[str, int] = {}
        for n in self._nodes.values():
            kinds[n.kind] = kinds.get(n.kind, 0) + 1
        relations: dict[str, int] = {}
        for e in self._edges:
            relations[e.relation] = relations.get(e.relation, 0) + 1
        return {"nodes": len(self._nodes), "edges": len(self._edges), "kinds": kinds, "relations": relations}
