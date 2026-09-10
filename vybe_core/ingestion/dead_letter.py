from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol
from uuid import UUID, uuid4

from vybe_core.ingestion.envelope import IngestionEnvelope
from vybe_core.ingestion.retry import FailureRecord


@dataclass(frozen=True, slots=True)
class DeadLetterEntry:
    envelope: IngestionEnvelope
    failure: FailureRecord
    failed_at: datetime
    id: UUID = field(default_factory=uuid4)

    def __post_init__(self) -> None:
        if self.failed_at.tzinfo is None:
            raise ValueError("failed_at must be timezone-aware")


class DeadLetterStore(Protocol):
    def append(self, entry: DeadLetterEntry) -> None: ...

    def get(self, entry_id: UUID) -> DeadLetterEntry | None: ...

    def list_for_provider(self, provider: str, *, limit: int = 100) -> tuple[DeadLetterEntry, ...]: ...
