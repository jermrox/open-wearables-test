from __future__ import annotations

from dataclasses import replace
from typing import Callable

from vybe_core.models.evidence import Evidence


class UnsupportedUnitError(ValueError):
    pass


_UNIT_ALIASES: dict[str, str] = {
    "bpm": "bpm",
    "beats/min": "bpm",
    "beats_per_minute": "bpm",
    "ms": "ms",
    "millisecond": "ms",
    "milliseconds": "ms",
    "%": "%",
    "percent": "%",
    "percentage": "%",
    "count": "count",
    "steps": "count",
    "s": "s",
    "sec": "s",
    "seconds": "s",
    "min": "min",
    "minutes": "min",
    "h": "h",
    "hr": "h",
    "hours": "h",
    "m": "m",
    "meter": "m",
    "meters": "m",
    "km": "km",
    "kilometer": "km",
    "kilometers": "km",
    "c": "degC",
    "°c": "degC",
    "degc": "degC",
    "celsius": "degC",
    "f": "degF",
    "°f": "degF",
    "degf": "degF",
    "fahrenheit": "degF",
}


def canonical_unit(unit: str | None) -> str | None:
    if unit is None:
        return None
    key = unit.strip().lower()
    try:
        return _UNIT_ALIASES[key]
    except KeyError as exc:
        raise UnsupportedUnitError(f"unsupported unit: {unit}") from exc


def _identity(value: float) -> float:
    return value


def _fahrenheit_to_celsius(value: float) -> float:
    return (value - 32.0) * (5.0 / 9.0)


def _hours_to_minutes(value: float) -> float:
    return value * 60.0


def _seconds_to_minutes(value: float) -> float:
    return value / 60.0


def _kilometers_to_meters(value: float) -> float:
    return value * 1000.0


MetricRule = tuple[str, dict[str, Callable[[float], float]]]


_METRIC_RULES: dict[str, MetricRule] = {
    "heart_rate": ("bpm", {"bpm": _identity}),
    "resting_heart_rate": ("bpm", {"bpm": _identity}),
    "hrv_rmssd": ("ms", {"ms": _identity}),
    "spo2": ("%", {"%": _identity}),
    "sleep_duration": ("min", {"min": _identity, "h": _hours_to_minutes, "s": _seconds_to_minutes}),
    "steps": ("count", {"count": _identity}),
    "distance": ("m", {"m": _identity, "km": _kilometers_to_meters}),
    "skin_temperature": ("degC", {"degC": _identity, "degF": _fahrenheit_to_celsius}),
}


def normalize_evidence(evidence: Evidence) -> Evidence:
    """Normalize a known metric to its canonical unit.

    Unknown metrics are preserved only when their unit is already canonicalizable;
    no guessed conversion is attempted. Non-numeric values are never converted.
    """

    unit = canonical_unit(evidence.unit)
    rule = _METRIC_RULES.get(evidence.metric)

    if rule is None:
        return replace(evidence, unit=unit)

    target_unit, conversions = rule
    if unit is None:
        raise UnsupportedUnitError(f"metric {evidence.metric} requires a unit")
    if unit not in conversions:
        raise UnsupportedUnitError(
            f"metric {evidence.metric} does not support conversion from {unit} to {target_unit}"
        )
    if not isinstance(evidence.value, (int, float)) or isinstance(evidence.value, bool):
        raise TypeError(f"metric {evidence.metric} requires a numeric value")

    converted = conversions[unit](float(evidence.value))
    return replace(evidence, value=converted, unit=target_unit)
