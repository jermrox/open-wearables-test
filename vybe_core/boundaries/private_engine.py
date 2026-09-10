from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class RawSignalBatch:
    """Internal-only signal container.

    This type is deliberately not referenced by the public developer API. It
    represents proprietary device/signal-processing inputs that may include
    raw samples, calibration context, and implementation-specific metadata.
    """

    payload: bytes
    sample_rate_hz: float | None = None
    firmware_version: str | None = None
    device_model: str | None = None


@dataclass(frozen=True, slots=True)
class ProcessedSignal:
    metric: str
    value: float
    unit: str
    confidence: float | None = None


class ProprietarySignalEngine(Protocol):
    """Private engine seam implemented by Vybe-owned signal-processing code."""

    def process(self, batch: RawSignalBatch) -> tuple[ProcessedSignal, ...]: ...
