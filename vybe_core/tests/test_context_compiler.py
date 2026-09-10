from datetime import datetime, timedelta, timezone

from vybe_core.context.compiler import ContextCompiler
from vybe_core.models.evidence import (
    Evidence,
    EvidenceProvenance,
    EvidenceQuality,
    EvidenceSource,
    SourceType,
)


def make_evidence(metric: str, confidence: float, seconds_ago: int) -> Evidence:
    now = datetime.now(timezone.utc)
    return Evidence(
        metric=metric,
        value=1,
        recorded_at=now - timedelta(seconds=seconds_ago),
        source=EvidenceSource(source_type=SourceType.DEVICE, provider="vybe_band"),
        provenance=EvidenceProvenance(
            ingested_at=now,
            processor="test",
            processing_version="1.0.0",
        ),
        quality=EvidenceQuality(confidence=confidence),
    )


def test_compiler_bounds_context_and_reports_omissions() -> None:
    evidence = [
        make_evidence("a", 0.9, 10),
        make_evidence("b", 0.8, 5),
        make_evidence("c", 0.7, 1),
    ]
    compiled = ContextCompiler(max_items=2).compile("why?", evidence)
    assert len(compiled.items) == 2
    assert compiled.omitted_count == 1


def test_compiler_prefers_higher_confidence_then_recency() -> None:
    evidence = [
        make_evidence("older_high", 0.9, 60),
        make_evidence("newer_high", 0.9, 1),
        make_evidence("lower", 0.5, 0),
    ]
    compiled = ContextCompiler(max_items=3).compile("why?", evidence)
    assert [item.metric for item in compiled.items] == ["newer_high", "older_high", "lower"]
