from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID, uuid4


class IngestionMode(str, Enum):
    PULL = "pull"
    WEBHOOK = "webhook"
    SDK_PUSH = "sdk_push"
    FILE_IMPORT = "file_import"
    DEVICE_SYNC = "device_sync"
    FHIR = "fhir"
    MANUAL = "manual"


@dataclass(frozen=True, slots=True)
class IngestionEnvelope:
    """Source-neutral wrapper around an inbound payload.

    This object captures transport metadata before any provider-specific parsing
    or normalization occurs. Raw payloads remain untouched at this boundary.
    """

    person_id: UUID
    provider: str
    mode: IngestionMode
    received_at: datetime
    payload: bytes | str | dict[str, Any] | list[Any]
    external_event_id: str | None = None
    connection_id: UUID | None = None
    headers: dict[str, str] = field(default_factory=dict)
    id: UUID = field(default_factory=uuid4)

    def __post_init__(self) -> None:
        if not self.provider.strip():
            raise ValueError("provider must not be empty")
        if self.received_at.tzinfo is None:
            raise ValueError("received_at must be timezone-aware")
