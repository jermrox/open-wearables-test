from datetime import datetime, timezone

import pytest

from vybe_core.graph.builders import InterventionRecord, add_evidence, add_intervention, link_observed_after
from vybe_core.graph.models import EdgeKind, GraphEdge, GraphNode, HealthGraph, NodeKind
from vybe_core.models.evidence import Evidence, EvidenceProvenance, EvidenceSource, SourceType


def _evidence(hour: int = 8) -> Evidence:
    recorded = datetime(2026, 9, 10, hour, tzinfo=timezone.utc)
    return Evidence(
        metric="heart_rate",
        value=62,
        unit="bpm",
        recorded_at=recorded,
        source=EvidenceSource(source_type=SourceType.DEVICE, provider="test-device"),
        provenance=EvidenceProvenance(
            ingested_at=recorded,
            processor="test",
            processing_version="1",
        ),
    )


def test_evidence_node_requires_evidence() -> None:
    with pytest.raises(ValueError):
        GraphNode(kind=NodeKind.EVIDENCE, recorded_at=datetime.now(timezone.utc))


def test_edge_requires_existing_endpoints() -> None:
    graph = HealthGraph()
    node = add_evidence(graph, _evidence())
    missing = GraphNode(kind=NodeKind.CONTEXT, recorded_at=datetime.now(timezone.utc), label="context")
    edge = GraphEdge(source_id=node.id, target_id=missing.id, kind=EdgeKind.ASSOCIATED_WITH)
    with pytest.raises(ValueError):
        graph.add_edge(edge)


def test_observed_after_rejects_pre_intervention_measurement() -> None:
    graph = HealthGraph()
    evidence_node = add_evidence(graph, _evidence(hour=8))
    intervention_node = add_intervention(
        graph,
        InterventionRecord(
            label="Earlier bedtime",
            started_at=datetime(2026, 9, 10, 9, tzinfo=timezone.utc),
            metadata={},
        ),
    )
    with pytest.raises(ValueError):
        link_observed_after(graph, intervention_node.id, evidence_node.id)


def test_observed_after_links_post_intervention_measurement() -> None:
    graph = HealthGraph()
    intervention_node = add_intervention(
        graph,
        InterventionRecord(
            label="Earlier bedtime",
            started_at=datetime(2026, 9, 10, 7, tzinfo=timezone.utc),
            metadata={"source": "user"},
        ),
    )
    evidence_node = add_evidence(graph, _evidence(hour=8))
    edge = link_observed_after(graph, intervention_node.id, evidence_node.id)

    assert edge.kind is EdgeKind.OBSERVED_AFTER
    assert graph.neighbors(intervention_node.id, EdgeKind.OBSERVED_AFTER) == (evidence_node,)
