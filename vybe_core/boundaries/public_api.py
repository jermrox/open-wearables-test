from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Protocol
from uuid import UUID


class PublicMetric(str, Enum):
    HEART_RATE = "heart_rate"
    HRV_RMSSD = "hrv_rmssd"
    SPO2 = "spo2"
    SLEEP_DURATION = "sleep_duration"
    STEPS = "steps"
    RESPIRATORY_RATE = "respiratory_rate"


@dataclass(frozen=True, slots=True)
class MetricPoint:
    metric: PublicMetric
    value: float
    unit: str
    recorded_at: datetime
    confidence: float | None = None

    def __post_init__(self) -> None:
        if self.recorded_at.tzinfo is None:
            raise ValueError("recorded_at must be timezone-aware")
        if self.confidence is not None and not 0.0 <= self.confidence <= 1.0:
            raise ValueError("confidence must be between 0 and 1")


@dataclass(frozen=True, slots=True)
class MetricQuery:
    person_id: UUID
    metric: PublicMetric
    start_at: datetime
    end_at: datetime

    def __post_init__(self) -> None:
        if self.start_at.tzinfo is None or self.end_at.tzinfo is None:
            raise ValueError("query timestamps must be timezone-aware")
        if self.end_at < self.start_at:
            raise ValueError("end_at must be on or after start_at")


class DeveloperHealthAPI(Protocol):
    """Commercially exposed health-data capability surface.

    This contract intentionally exposes normalized outputs only. It does not
    expose device protocol frames, firmware behavior, raw signal-processing
    internals, calibration constants, or proprietary model implementation.
    """

    def query_metric(self, query: MetricQuery) -> tuple[MetricPoint, ...]: ...

    def latest_metric(self, person_id: UUID, metric: PublicMetric) -> MetricPoint | None: ...
