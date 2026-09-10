from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Iterable

from vybe_core.graph.models import GraphNode, HealthGraph, NodeKind


@dataclass(frozen=True, slots=True)
class GraphQuery:
    metric: str | None = None
    start: datetime | None = None
    end: datetime | None = None
    kinds: tuple[NodeKind, ...] = ()
    limit: int | None = None

    def __post_init__(self) -> None:
        for boundary in (self.start, self.end):
            if boundary is not None and boundary.tzinfo is None:
                raise ValueError("query time boundaries must be timezone-aware")
        if self.start is not None and self.end is not None and self.start > self.end:
            raise ValueError("start must not be after end")
        if self.limit is not None and self.limit <= 0:
            raise ValueError("limit must be positive")


def _matches(node: GraphNode, query: GraphQuery) -> bool:
    if query.kinds and node.kind not in query.kinds:
        return False
    if query.start is not None and node.recorded_at < query.start:
        return False
    if query.end is not None and node.recorded_at > query.end:
        return False
    if query.metric is not None:
        if node.kind is not NodeKind.EVIDENCE or node.evidence is None:
            return False
        if node.evidence.metric != query.metric:
            return False
    return True


def query_nodes(graph: HealthGraph, query: GraphQuery) -> tuple[GraphNode, ...]:
    matches: Iterable[GraphNode] = (node for node in graph.nodes.values() if _matches(node, query))
    ordered = sorted(matches, key=lambda node: (node.recorded_at, str(node.id)), reverse=True)
    if query.limit is not None:
        ordered = ordered[: query.limit]
    return tuple(ordered)
