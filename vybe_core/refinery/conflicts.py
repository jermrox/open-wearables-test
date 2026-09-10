from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from typing import Iterable

from vybe_core.models.evidence import Evidence


@dataclass(frozen=True, slots=True)
class Conflict:
    metric: str
    members: tuple[Evidence, ...]
    reason: str


@dataclass(frozen=True, slots=True)
class ConflictPolicy:
    time_tolerance: timedelta = timedelta(seconds=60)
    absolute_tolerance: dict[str, float] | None = None
    relative_tolerance: dict[str, float] | None = None

    def absolute_for(self, metric: str) -> float:
        defaults = {
            "heart_rate": 5.0,
            "resting_heart_rate": 5.0,
            "hrv_rmssd": 10.0,
            "spo2": 2.0,
            "sleep_duration": 15.0,
            "steps": 100.0,
            "distance": 100.0,
            "skin_temperature": 0.5,
        }
        if self.absolute_tolerance and metric in self.absolute_tolerance:
            return self.absolute_tolerance[metric]
        return defaults.get(metric, 0.0)

    def relative_for(self, metric: str) -> float:
        defaults = {
            "heart_rate": 0.10,
            "resting_heart_rate": 0.10,
            "hrv_rmssd": 0.20,
            "spo2": 0.03,
            "sleep_duration": 0.05,
            "steps": 0.05,
            "distance": 0.05,
            "skin_temperature": 0.02,
        }
        if self.relative_tolerance and metric in self.relative_tolerance:
            return self.relative_tolerance[metric]
        return defaults.get(metric, 0.0)


def _numeric(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


def _materially_differs(a: Evidence, b: Evidence, policy: ConflictPolicy) -> bool:
    av = _numeric(a.value)
    bv = _numeric(b.value)
    if av is None or bv is None:
        return a.value != b.value

    difference = abs(av - bv)
    if difference <= policy.absolute_for(a.metric):
        return False

    scale = max(abs(av), abs(bv), 1e-12)
    return difference / scale > policy.relative_for(a.metric)


def detect_conflicts(
    evidence: Iterable[Evidence],
    *,
    policy: ConflictPolicy | None = None,
) -> tuple[Conflict, ...]:
    """Find materially different near-simultaneous values from distinct sources.

    This function does not choose a winner. Selection belongs to the resolution
    layer so disagreement remains auditable.
    """

    active = policy or ConflictPolicy()
    items = sorted(tuple(evidence), key=lambda item: item.recorded_at)
    conflicts: list[Conflict] = []
    seen_pairs: set[tuple[str, str]] = set()

    for index, item in enumerate(items):
        for other in items[index + 1 :]:
            if other.recorded_at - item.recorded_at > active.time_tolerance:
                break
            if item.metric != other.metric or item.unit != other.unit:
                continue
            if item.source.provider == other.source.provider:
                continue
            pair_key = tuple(sorted((str(item.id), str(other.id))))
            if pair_key in seen_pairs:
                continue
            seen_pairs.add(pair_key)
            if _materially_differs(item, other, active):
                conflicts.append(
                    Conflict(
                        metric=item.metric,
                        members=(item, other),
                        reason="near-simultaneous cross-source values differ beyond configured tolerance",
                    )
                )

    return tuple(conflicts)
