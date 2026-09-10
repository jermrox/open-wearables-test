from datetime import datetime, timedelta, timezone

import pytest

from vybe_core.models.evidence import Evidence, EvidenceProvenance, EvidenceQuality, EvidenceSource, SourceType
from vybe_core.resolution.source_priority import ResolutionPolicy
from vybe_core.state.snapshot import build_personal_state_snapshot


def _evidence(metric: str, when: datetime, value: float, provider: str = "device", quality: float = 0.9) -> Evidence:
    return Evidence(
        metric=metric,
        value=value,
        unit="ms" if metric == "hrv_rmssd" else "bpm",
        recorded_at=when,
        source=EvidenceSource(source_type=SourceType.DEVICE, provider=provider),
        provenance=EvidenceProvenance(
            ingested_at=when,
            processor="test",
            processing_version="1",
        ),
        quality=EvidenceQuality(signal_quality=quality, confidence=quality),
    )


def test_snapshot_selects_best_latest_source_and_builds_baseline_delta() -> None:
    now = datetime(2026, 9, 10, 12, tzinfo=timezone.utc)
    history = [
        _evidence("hrv_rmssd", now - timedelta(days=day), 50 + (day % 2))
        for day in range(1, 9)
    ]
    latest_low_quality = _evidence("hrv_rmssd", now, 40, provider="low", quality=0.5)
    latest_high_quality = _evidence("hrv_rmssd", now, 42, provider="high", quality=0.95)

    snapshot = build_personal_state_snapshot(
        generated_at=now,
        evidence=[*history, latest_low_quality, latest_high_quality],
        metrics=["hrv_rmssd"],
        resolution_policy=ResolutionPolicy(),
        baseline_window_size=7,
        baseline_minimum_samples=7,
    )

    assert len(snapshot.metrics) == 1
    state = snapshot.metrics[0]
    assert state.current.id == latest_high_quality.id
    assert state.baseline_delta is not None
    assert state.baseline_delta.metric == "hrv_rmssd.baseline_delta"
    assert state.baseline_delta.provenance.parent_evidence_ids[0] == latest_high_quality.id
    assert len(state.baseline_delta.provenance.parent_evidence_ids) == 8


def test_snapshot_does_not_create_baseline_without_enough_history() -> None:
    now = datetime(2026, 9, 10, 12, tzinfo=timezone.utc)
    evidence = [_evidence("heart_rate", now - timedelta(days=day), 60 + day) for day in range(3)]
    evidence.append(_evidence("heart_rate", now, 61))

    snapshot = build_personal_state_snapshot(
        generated_at=now,
        evidence=evidence,
        metrics=["heart_rate"],
        baseline_minimum_samples=7,
    )

    assert snapshot.metrics[0].baseline_delta is None


def test_snapshot_ignores_future_evidence() -> None:
    now = datetime(2026, 9, 10, 12, tzinfo=timezone.utc)
    current = _evidence("heart_rate", now, 61)
    future = _evidence("heart_rate", now + timedelta(hours=1), 99)

    snapshot = build_personal_state_snapshot(
        generated_at=now,
        evidence=[current, future],
        metrics=["heart_rate"],
    )

    assert snapshot.metrics[0].current.id == current.id


def test_snapshot_validates_baseline_window() -> None:
    with pytest.raises(ValueError):
        build_personal_state_snapshot(
            generated_at=datetime.now(timezone.utc),
            evidence=[],
            metrics=[],
            baseline_window_size=5,
            baseline_minimum_samples=7,
        )
