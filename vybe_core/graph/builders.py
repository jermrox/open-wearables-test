from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from vybe_core.graph.models import EdgeKind, GraphEdge, GraphNode, HealthGraph, NodeKind
from vybe_core.models.evidence import Evidence


@dataclass(frozen=True, slots=True)
class InterventionRecord:
    label: str
    started_at: datetime
    metadata: dict[str, str | int | float | bool]

    def __post_init__(self) -> None:
        if self.started_at.tzinfo is None:
            raise ValueError("started_at must be timezone-aware")
        if not self.label.strip():
            raise ValueError("label must not be empty")


def add_evidence(graph: HealthGraph, evidence: Evidence) -> GraphNode:
    node = GraphNode(kind=NodeKind.EVIDENCE, recorded_at=evidence.recorded_at, evidence=evidence)
    graph.add_node(node)
    return node


def add_intervention(graph: HealthGraph, intervention: InterventionRecord) -> GraphNode:
    node = GraphNode(
        kind=NodeKind.INTERVENTION,
        recorded_at=intervention.started_at,
        label=intervention.label,
        metadata=dict(intervention.metadata),
    )
    graph.add_node(node)
    return node


def link_observed_after(graph: HealthGraph, intervention_node_id: UUID, evidence_node_id: UUID) -> GraphEdge:
    intervention = graph.nodes.get(intervention_node_id)
    evidence = graph.nodes.get(evidence_node_id)
    if intervention is None or evidence is None:
        raise ValueError("both nodes must exist")
    if intervention.kind is not NodeKind.INTERVENTION:
        raise ValueError("source must be an intervention")
    if evidence.kind is not NodeKind.EVIDENCE:
        raise ValueError("target must be evidence")
    if evidence.recorded_at < intervention.recorded_at:
        raise ValueError("post-intervention evidence cannot precede the intervention")

    edge = GraphEdge(
        source_id=intervention_node_id,
        target_id=evidence_node_id,
        kind=EdgeKind.OBSERVED_AFTER,
    )
    graph.add_edge(edge)
    return edge
