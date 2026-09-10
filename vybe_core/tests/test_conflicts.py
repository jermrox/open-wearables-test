from datetime import datetime, timedelta, timezone

from vybe_core.models.evidence import (
    Evidence,
    EvidenceProvenance,
    EvidenceQuality,
    EvidenceSource,
    SourceType,
)
from vybe_core.refinery.conflicts import detect_conflicts


def make_evidence(*, value: float, provider: str, at: datetime):
    return Evidence(
        metric="heart_rate",
        value=value,
        unit="bpm",
        recorded_at=at,
        source=EvidenceSource(source_type=SourceType.DEVICE, provider=provider),
        provenance=EvidenceProvenance(
            ingested_at=at,
            processor="test",
            processing_version="1",
        ),
        quality=EvidenceQuality(signal_quality=0.9, confidence=0.9),
    )


def test_detects_material_cross_source_disagreement():
    now = datetime(2026, 9, 10, 12, 0, tzinfo=timezone.utc)
    conflicts = detect_conflicts(
        [
            make_evidence(value=70, provider="vybe_band", at=now),
            make_evidence(value=95, provider="apple_health", at=now),
        ]
    )
    assert len(conflicts) == 1


def test_small_difference_is_not_a_conflict():
    now = datetime(2026, 9, 10, 12, 0, tzinfo=timezone.utc)
    conflicts = detect_conflicts(
        [
            make_evidence(value=70, provider="vybe_band", at=now),
            make_evidence(value=73, provider="apple_health", at=now),
        ]
    )
    assert conflicts == ()


def test_measurements_outside_time_window_are_not_compared():
    now = datetime(2026, 9, 10, 12, 0, tzinfo=timezone.utc)
    conflicts = detect_conflicts(
        [
            make_evidence(value=70, provider="vybe_band", at=now),
            make_evidence(value=95, provider="apple_health", at=now + timedelta(minutes=5)),
        ]
    )
    assert conflicts == ()
