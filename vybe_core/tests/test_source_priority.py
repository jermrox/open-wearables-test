from datetime import datetime, timedelta, timezone

from vybe_core.models.evidence import (
    Evidence,
    EvidenceProvenance,
    EvidenceQuality,
    EvidenceSource,
    SourceType,
)
from vybe_core.resolution.source_priority import ResolutionPolicy, resolve_best


def make(metric: str, provider: str, source_type: SourceType, quality: float, confidence: float, age_s: int) -> Evidence:
    now = datetime.now(timezone.utc)
    return Evidence(
        metric=metric,
        value=1,
        recorded_at=now - timedelta(seconds=age_s),
        source=EvidenceSource(source_type=source_type, provider=provider),
        provenance=EvidenceProvenance(
            ingested_at=now,
            processor="test",
            processing_version="1.0.0",
        ),
        quality=EvidenceQuality(signal_quality=quality, confidence=confidence),
    )


def test_quality_beats_provider_preference() -> None:
    lower_quality_preferred = make("hrv_rmssd", "preferred", SourceType.DEVICE, 0.60, 0.95, 0)
    higher_quality_other = make("hrv_rmssd", "other", SourceType.HEALTH_STORE, 0.95, 0.95, 10)
    policy = ResolutionPolicy(metric_provider_priority={"hrv_rmssd": {"preferred": 1000}})
    assert resolve_best([lower_quality_preferred, higher_quality_other], policy).selected is higher_quality_other


def test_metric_specific_provider_policy_breaks_equal_quality_tie() -> None:
    band = make("sleep_duration", "vybe_band", SourceType.DEVICE, 0.95, 0.95, 10)
    health_store = make("sleep_duration", "apple_health", SourceType.HEALTH_STORE, 0.95, 0.95, 0)
    policy = ResolutionPolicy(metric_provider_priority={"sleep_duration": {"vybe_band": 50, "apple_health": 10}})
    assert resolve_best([health_store, band], policy).selected is band


def test_mixed_metrics_are_rejected() -> None:
    a = make("heart_rate", "vybe_band", SourceType.DEVICE, 0.9, 0.9, 0)
    b = make("spo2", "vybe_band", SourceType.DEVICE, 0.9, 0.9, 0)
    try:
        resolve_best([a, b])
    except ValueError as exc:
        assert "same metric" in str(exc)
    else:
        raise AssertionError("mixed metrics should not resolve")
