from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from uuid import UUID, uuid4

from vybe_core.models.evidence import Evidence


class NodeKind(str, Enum):
    EVIDENCE = "evidence"
    INTERVENTION = "intervention"
    OUTCOME = "outcome"
    CONTEXT = "context"


class EdgeKind(str, Enum):
    PRECEDES = "precedes"
    FOLLOWS = "follows"
    ASSOCIATED_WITH = "associated_with"
    DERIVED_FROM = "derived_from"
    APPLIED_TO = "applied_to"
    OBSERVED_AFTER = "observed_after"


@dataclass(frozen=True, slots=True)
class GraphNode:
    kind: NodeKind
    recorded_at: datetime
    evidence: Evidence | None = None
    label: str | None = None
    metadata: dict[str, str | int | float | bool] = field(default_factory=dict)
    id: UUID = field(default_factory=uuid4)

    def __post_init__(self) -> None:
        if self.recorded_at.tzinfo is None:
            raise ValueError("recorded_at must be timezone-aware")
        if self.kind is NodeKind.EVIDENCE and self.evidence is None:
            raise ValueError("evidence nodes require evidence")
        if self.kind is not NodeKind.EVIDENCE and self.evidence is not None:
            raise ValueError("only evidence nodes may carry Evidence")


@dataclass(frozen=True, slots=True)
class GraphEdge:
    source_id: UUID
    target_id: UUID
    kind: EdgeKind
    metadata: dict[str, str | int | float | bool] = field(default_factory=dict)
    id: UUID = field(default_factory=uuid4)


@dataclass(slots=True)
class HealthGraph:
    nodes: dict[UUID, GraphNode] = field(default_factory=dict)
    edges: dict[UUID, GraphEdge] = field(default_factory=dict)

    def add_node(self, node: GraphNode) -> None:
        if node.id in self.nodes:
            raise ValueError(f"node already exists: {node.id}")
        self.nodes[node.id] = node

    def add_edge(self, edge: GraphEdge) -> None:
        if edge.id in self.edges:
            raise ValueError(f"edge already exists: {edge.id}")
        if edge.source_id not in self.nodes or edge.target_id not in self.nodes:
            raise ValueError("edge endpoints must already exist")
        self.edges[edge.id] = edge

    def neighbors(self, node_id: UUID, kind: EdgeKind | None = None) -> tuple[GraphNode, ...]:
        if node_id not in self.nodes:
            raise KeyError(node_id)
        target_ids = [
            edge.target_id
            for edge in self.edges.values()
            if edge.source_id == node_id and (kind is None or edge.kind is kind)
        ]
        return tuple(self.nodes[target_id] for target_id in target_ids)
