from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from statistics import median
from typing import Sequence

from vybe_core.models.evidence import (
    Evidence,
    EvidenceKind,
    EvidenceProvenance,
    EvidenceQuality,
    EvidenceSource,
    SourceType,
)


@dataclass(frozen=True, slots=True)
class BaselineResult:
    median_value: float
    median_absolute_deviation: float
    sample_count: int


def robust_baseline(samples: Sequence[Evidence], *, minimum_samples: int = 7) -> BaselineResult:
    """Compute a robust personal baseline from numeric observations.

    Uses the median and median absolute deviation (MAD). It intentionally does
    not infer population norms or clinical thresholds.
    """
    numeric = [float(item.value) for item in samples if isinstance(item.value, (int, float)) and not isinstance(item.value, bool)]
    if len(numeric) < minimum_samples:
        raise ValueError(f"at least {minimum_samples} numeric samples are required")

    center = median(numeric)
    mad = median(abs(value - center) for value in numeric)
    return BaselineResult(median_value=center, median_absolute_deviation=mad, sample_count=len(numeric))


def derive_baseline_delta(
    current: Evidence,
    history: Sequence[Evidence],
    *,
    processing_version: str = "1.0.0",
    minimum_samples: int = 7,
) -> Evidence:
    """Create lineage-preserving relative deviation from a personal baseline."""
    if not isinstance(current.value, (int, float)) or isinstance(current.value, bool):
        raise ValueError("current evidence must have a numeric value")

    same_metric = [item for item in history if item.metric == current.metric and item.id != current.id]
    baseline = robust_baseline(same_metric, minimum_samples=minimum_samples)

    if baseline.median_value == 0:
        raise ValueError("relative baseline delta is undefined for a zero median")

    delta = (float(current.value) - baseline.median_value) / abs(baseline.median_value)
    parents = (current.id, *(item.id for item in same_metric))
    confidence_values = [
        item.quality.confidence
        for item in (current, *same_metric)
        if item.quality.confidence is not None
    ]
    confidence = min(confidence_values) if confidence_values else None

    return Evidence(
        metric=f"{current.metric}.baseline_delta",
        value=delta,
        unit="ratio",
        recorded_at=current.recorded_at,
        source=EvidenceSource(source_type=SourceType.DERIVED, provider="vybe_core"),
        provenance=EvidenceProvenance(
            ingested_at=datetime.now(timezone.utc),
            processor="robust_baseline_delta",
            processing_version=processing_version,
            parent_evidence_ids=parents,
        ),
        quality=EvidenceQuality(confidence=confidence),
        kind=EvidenceKind.DERIVATION,
        metadata={
            "baseline_median": baseline.median_value,
            "baseline_mad": baseline.median_absolute_deviation,
            "baseline_sample_count": baseline.sample_count,
        },
    )
