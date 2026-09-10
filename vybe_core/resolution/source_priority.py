from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Iterable

from vybe_core.models.evidence import Evidence, SourceType


DEFAULT_SOURCE_PRIORITY: dict[SourceType, int] = {
    SourceType.CLINICAL: 600,
    SourceType.DEVICE: 500,
    SourceType.HEALTH_STORE: 400,
    SourceType.CLOUD_PROVIDER: 300,
    SourceType.ENVIRONMENT: 200,
    SourceType.MANUAL: 100,
    SourceType.DERIVED: 50,
}


@dataclass(frozen=True, slots=True)
class ResolutionPolicy:
    """Metric-aware policy for choosing among overlapping evidence.

    Higher provider/source scores are preferred. Quality and confidence remain
    independent signals and are not overwritten by provider preference.
    """

    source_priority: dict[SourceType, int] = field(default_factory=lambda: dict(DEFAULT_SOURCE_PRIORITY))
    provider_priority: dict[str, int] = field(default_factory=dict)
    metric_provider_priority: dict[str, dict[str, int]] = field(default_factory=dict)

    def provider_score(self, metric: str, provider: str) -> int:
        metric_scores = self.metric_provider_priority.get(metric, {})
        if provider in metric_scores:
            return metric_scores[provider]
        return self.provider_priority.get(provider, 0)


@dataclass(frozen=True, slots=True)
class ResolutionResult:
    selected: Evidence
    alternatives: tuple[Evidence, ...]
    reason: str


def _score(evidence: Evidence, policy: ResolutionPolicy) -> tuple[float, float, int, int, datetime]:
    quality = evidence.quality.signal_quality if evidence.quality.signal_quality is not None else -1.0
    confidence = evidence.quality.confidence if evidence.quality.confidence is not None else -1.0
    provider = policy.provider_score(evidence.metric, evidence.source.provider)
    source = policy.source_priority.get(evidence.source.source_type, 0)
    return (quality, confidence, provider, source, evidence.recorded_at)


def resolve_best(evidence: Iterable[Evidence], policy: ResolutionPolicy | None = None) -> ResolutionResult:
    candidates = tuple(evidence)
    if not candidates:
        raise ValueError("at least one evidence candidate is required")

    metric = candidates[0].metric
    if any(item.metric != metric for item in candidates):
        raise ValueError("all evidence candidates must represent the same metric")

    active_policy = policy or ResolutionPolicy()
    ranked = sorted(candidates, key=lambda item: _score(item, active_policy), reverse=True)
    selected = ranked[0]

    return ResolutionResult(
        selected=selected,
        alternatives=tuple(ranked[1:]),
        reason=(
            "selected by signal quality, confidence, metric/provider policy, "
            "source class, then recency"
        ),
    )
