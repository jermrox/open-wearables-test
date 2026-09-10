from datetime import datetime, timedelta, timezone

import pytest

from vybe_core.derivations.baseline import derive_baseline_delta, robust_baseline
from vybe_core.models.evidence import (
    Evidence,
    EvidenceKind,
    EvidenceProvenance,
    EvidenceQuality,
    EvidenceSource,
    SourceType,
)


def sample(metric: str, value: float, days_ago: int, confidence: float = 0.95) -> Evidence:
    now = datetime.now(timezone.utc)
    return Evidence(
        metric=metric,
        value=value,
        unit="ms",
        recorded_at=now - timedelta(days=days_ago),
        source=EvidenceSource(source_type=SourceType.DEVICE, provider="vybe_band"),
        provenance=EvidenceProvenance(
            ingested_at=now,
            processor="test",
            processing_version="1.0.0",
        ),
        quality=EvidenceQuality(confidence=confidence),
    )


def test_robust_baseline_resists_single_outlier() -> None:
    history = [sample("hrv_rmssd", value, i) for i, value in enumerate([40, 41, 39, 40, 42, 38, 200])]
    baseline = robust_baseline(history)
    assert baseline.median_value == 40
    assert baseline.median_absolute_deviation == 1


def test_baseline_requires_minimum_history() -> None:
    with pytest.raises(ValueError):
        robust_baseline([sample("hrv_rmssd", 40, 1)])


def test_derived_delta_preserves_lineage_and_confidence() -> None:
    current = sample("hrv_rmssd", 36, 0, confidence=0.90)
    history = [sample("hrv_rmssd", value, i + 1, confidence=0.95) for i, value in enumerate([40, 41, 39, 40, 42, 38, 40])]
    derived = derive_baseline_delta(current, history)

    assert derived.kind is EvidenceKind.DERIVATION
    assert derived.metric == "hrv_rmssd.baseline_delta"
    assert derived.value == pytest.approx(-0.10)
    assert derived.quality.confidence == 0.90
    assert current.id in derived.provenance.parent_evidence_ids
    assert derived.metadata["baseline_median"] == 40
