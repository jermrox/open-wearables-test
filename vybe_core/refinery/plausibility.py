from __future__ import annotations

from dataclasses import dataclass

from vybe_core.models.evidence import Evidence


@dataclass(frozen=True, slots=True)
class PlausibilityResult:
    accepted: bool
    reasons: tuple[str, ...] = ()


# These are broad engineering sanity bounds, not diagnostic thresholds.
# They prevent impossible/corrupted values from entering downstream analytics.
_NUMERIC_BOUNDS: dict[str, tuple[float, float]] = {
    "heart_rate": (20.0, 260.0),
    "resting_heart_rate": (20.0, 220.0),
    "hrv_rmssd": (0.0, 500.0),
    "spo2": (50.0, 100.0),
    "sleep_duration": (0.0, 1440.0),
    "steps": (0.0, 200000.0),
    "distance": (0.0, 500000.0),
    "skin_temperature": (20.0, 45.0),
}


def check_plausibility(evidence: Evidence) -> PlausibilityResult:
    bounds = _NUMERIC_BOUNDS.get(evidence.metric)
    if bounds is None:
        return PlausibilityResult(accepted=True)

    if not isinstance(evidence.value, (int, float)) or isinstance(evidence.value, bool):
        return PlausibilityResult(False, ("non_numeric_value",))

    low, high = bounds
    value = float(evidence.value)
    reasons: list[str] = []
    if value < low:
        reasons.append("below_engineering_bound")
    if value > high:
        reasons.append("above_engineering_bound")

    return PlausibilityResult(accepted=not reasons, reasons=tuple(reasons))
