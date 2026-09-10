from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Iterable

from vybe_core.derivations.baseline import BaselineResult, derive_baseline_deviation
from vybe_core.models.evidence import Evidence
from vybe_core.resolution.source_priority import ResolutionPolicy, resolve_best


@dataclass(frozen=True, slots=True)
class MetricState:
    metric: str
    current: Evidence
    baseline: BaselineResult | None


@dataclass(frozen=True, slots=True)
class PersonalStateSnapshot:
    generated_at: datetime
    metrics: tuple[MetricState, ...]

    def __post_init__(self) -> None:
        if self.generated_at.tzinfo is None:
            raise ValueError("generated_at must be timezone-aware")


def build_personal_state_snapshot(
    *,
    generated_at: datetime,
    evidence: Iterable[Evidence],
    metrics: Iterable[str],
    resolution_policy: ResolutionPolicy | None = None,
    baseline_window_size: int = 14,
    baseline_minimum_samples: int = 7,
) -> PersonalStateSnapshot:
    if generated_at.tzinfo is None:
        raise ValueError("generated_at must be timezone-aware")

    all_evidence = tuple(evidence)
    states: list[MetricState] = []

    for metric in metrics:
        candidates = tuple(
            item
            for item in all_evidence
            if item.metric == metric and item.recorded_at <= generated_at
        )
        if not candidates:
            continue

        latest_time = max(item.recorded_at for item in candidates)
        latest_candidates = tuple(item for item in candidates if item.recorded_at == latest_time)
        current = resolve_best(latest_candidates, resolution_policy).selected

        historical = tuple(
            item
            for item in candidates
            if item.id != current.id and isinstance(item.value, (int, float))
        )

        baseline: BaselineResult | None = None
        if isinstance(current.value, (int, float)) and len(historical) >= baseline_minimum_samples:
            baseline = derive_baseline_deviation(
                current=current,
                history=historical,
                window_size=baseline_window_size,
                minimum_samples=baseline_minimum_samples,
            )

        states.append(MetricState(metric=metric, current=current, baseline=baseline))

    return PersonalStateSnapshot(
        generated_at=generated_at,
        metrics=tuple(states),
    )
