from datetime import datetime, timezone

import pytest

from vybe_core.models.evidence import (
    Evidence,
    EvidenceProvenance,
    EvidenceQuality,
    EvidenceSource,
    SourceType,
)
from vybe_core.refinery.pipeline import EvidenceRefinery


def make_evidence(*, metric: str, value: float, unit: str, provider: str = "vybe", source_record_id: str | None = None):
    now = datetime(2026, 9, 10, 12, 0, tzinfo=timezone.utc)
    return Evidence(
        metric=metric,
        value=value,
        unit=unit,
        recorded_at=now,
        source=EvidenceSource(
            source_type=SourceType.DEVICE,
            provider=provider,
            source_record_id=source_record_id,
        ),
        provenance=EvidenceProvenance(
            ingested_at=now,
            processor="test",
            processing_version="1",
        ),
        quality=EvidenceQuality(signal_quality=0.9, confidence=0.9),
    )


def test_normalizes_sleep_hours_to_minutes():
    result = EvidenceRefinery().process([make_evidence(metric="sleep_duration", value=7.5, unit="h")])
    assert len(result.accepted) == 1
    assert result.accepted[0].unit == "min"
    assert result.accepted[0].value == pytest.approx(450.0)


def test_rejects_impossible_spo2_without_silently_dropping_it():
    evidence = make_evidence(metric="spo2", value=150, unit="%")
    result = EvidenceRefinery().process([evidence])
    assert result.accepted == ()
    assert len(result.rejected) == 1
    assert result.rejected[0].evidence.id == evidence.id
    assert result.rejected[0].stage == "plausibility"


def test_unknown_conversion_is_rejected_instead_of_guessed():
    evidence = make_evidence(metric="heart_rate", value=70, unit="ms")
    result = EvidenceRefinery().process([evidence])
    assert result.accepted == ()
    assert result.rejected[0].stage == "normalization"


def test_same_provider_identical_record_is_grouped_as_duplicate():
    first = make_evidence(metric="heart_rate", value=70, unit="bpm", source_record_id="abc")
    second = make_evidence(metric="heart_rate", value=70, unit="bpm", source_record_id="abc")
    result = EvidenceRefinery().process([first, second])
    assert len(result.accepted) == 1
    assert len(result.duplicate_groups[0].duplicates) == 1


def test_cross_provider_measurements_are_not_deduplicated():
    band = make_evidence(metric="heart_rate", value=70, unit="bpm", provider="vybe_band")
    apple = make_evidence(metric="heart_rate", value=70, unit="bpm", provider="apple_health")
    result = EvidenceRefinery().process([band, apple])
    assert len(result.accepted) == 2
