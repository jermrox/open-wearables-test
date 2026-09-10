from datetime import datetime, timedelta, timezone

import pytest

from vybe_core.graph.builders import add_evidence
from vybe_core.graph.models import HealthGraph, NodeKind
from vybe_core.graph.query import GraphQuery, query_nodes
from vybe_core.models.evidence import Evidence, EvidenceProvenance, EvidenceSource, SourceType


def _evidence(metric: str, when: datetime, value: float) -> Evidence:
    return Evidence(
        metric=metric,
        value=value,
        unit="bpm" if metric == "heart_rate" else "ms",
        recorded_at=when,
        source=EvidenceSource(source_type=SourceType.DEVICE, provider="test-device"),
        provenance=EvidenceProvenance(
            ingested_at=when,
            processor="test",
            processing_version="1",
        ),
    )


def test_query_filters_metric_and_time_window() -> None:
    graph = HealthGraph()
    base = datetime(2026, 9, 10, 8, tzinfo=timezone.utc)
    add_evidence(graph, _evidence("heart_rate", base, 60))
    add_evidence(graph, _evidence("heart_rate", base + timedelta(hours=1), 65))
    add_evidence(graph, _evidence("hrv_rmssd", base + timedelta(hours=1), 42))

    results = query_nodes(
        graph,
        GraphQuery(
            metric="heart_rate",
            start=base + timedelta(minutes=30),
            end=base + timedelta(hours=2),
        ),
    )

    assert len(results) == 1
    assert results[0].evidence is not None
    assert results[0].evidence.value == 65


def test_query_returns_newest_first_and_respects_limit() -> None:
    graph = HealthGraph()
    base = datetime(2026, 9, 10, 8, tzinfo=timezone.utc)
    for hour in range(3):
        add_evidence(graph, _evidence("heart_rate", base + timedelta(hours=hour), 60 + hour))

    results = query_nodes(graph, GraphQuery(metric="heart_rate", limit=2))

    assert [node.evidence.value for node in results if node.evidence is not None] == [62, 61]


def test_query_rejects_naive_boundaries_and_invalid_ranges() -> None:
    with pytest.raises(ValueError):
        GraphQuery(start=datetime(2026, 9, 10, 8))

    aware = datetime(2026, 9, 10, 8, tzinfo=timezone.utc)
    with pytest.raises(ValueError):
        GraphQuery(start=aware + timedelta(hours=1), end=aware)


def test_query_can_filter_by_node_kind() -> None:
    graph = HealthGraph()
    when = datetime(2026, 9, 10, 8, tzinfo=timezone.utc)
    node = add_evidence(graph, _evidence("heart_rate", when, 60))

    results = query_nodes(graph, GraphQuery(kinds=(NodeKind.EVIDENCE,)))
    assert results == (node,)
