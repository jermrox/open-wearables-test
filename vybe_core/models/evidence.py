from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID, uuid4


class EvidenceKind(str, Enum):
    OBSERVATION = "observation"
    EVENT = "event"
    DERIVATION = "derivation"
    CONTEXT = "context"


class SourceType(str, Enum):
    DEVICE = "device"
    HEALTH_STORE = "health_store"
    CLOUD_PROVIDER = "cloud_provider"
    CLINICAL = "clinical"
    MANUAL = "manual"
    ENVIRONMENT = "environment"
    DERIVED = "derived"


@dataclass(frozen=True, slots=True)
class EvidenceSource:
    source_type: SourceType
    provider: str
    device_id: str | None = None
    sensor: str | None = None
    source_record_id: str | None = None
    firmware_version: str | None = None


@dataclass(frozen=True, slots=True)
class EvidenceQuality:
    signal_quality: float | None = None
    confidence: float | None = None
    completeness: float | None = None
    flags: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for value in (self.signal_quality, self.confidence, self.completeness):
            if value is not None and not 0.0 <= value <= 1.0:
                raise ValueError("quality values must be between 0 and 1")


@dataclass(frozen=True, slots=True)
class EvidenceProvenance:
    ingested_at: datetime
    processor: str
    processing_version: str
    raw_sha256: str | None = None
    parent_evidence_ids: tuple[UUID, ...] = ()


@dataclass(frozen=True, slots=True)
class Evidence:
    metric: str
    recorded_at: datetime
    source: EvidenceSource
    provenance: EvidenceProvenance
    kind: EvidenceKind = EvidenceKind.OBSERVATION
    value: float | int | str | bool | None = None
    unit: str | None = None
    quality: EvidenceQuality = field(default_factory=EvidenceQuality)
    metadata: dict[str, Any] = field(default_factory=dict)
    id: UUID = field(default_factory=uuid4)

    def __post_init__(self) -> None:
        if not self.metric.strip():
            raise ValueError("metric must not be empty")
        if self.recorded_at.tzinfo is None:
            raise ValueError("recorded_at must be timezone-aware")
        if self.provenance.ingested_at.tzinfo is None:
            raise ValueError("ingested_at must be timezone-aware")
        if self.kind is EvidenceKind.DERIVATION and not self.provenance.parent_evidence_ids:
            raise ValueError("derived evidence must reference parent evidence")
