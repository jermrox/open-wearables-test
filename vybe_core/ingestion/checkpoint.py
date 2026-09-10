from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True, slots=True)
class SyncCheckpoint:
    person_id: UUID
    provider: str
    stream: str
    cursor: str | None
    updated_at: datetime

    def __post_init__(self) -> None:
        if not self.provider.strip():
            raise ValueError("provider must not be empty")
        if not self.stream.strip():
            raise ValueError("stream must not be empty")
        if self.updated_at.tzinfo is None:
            raise ValueError("updated_at must be timezone-aware")


class CheckpointStore(ABC):
    """Durable sync-progress boundary.

    A provider may expose timestamps, opaque cursors, pagination tokens, or no
    cursor at all. Vybe stores the provider's cursor as an opaque value and keeps
    cursor semantics inside the provider adapter.
    """

    @abstractmethod
    async def get(self, person_id: UUID, provider: str, stream: str) -> SyncCheckpoint | None:
        raise NotImplementedError

    @abstractmethod
    async def put(self, checkpoint: SyncCheckpoint) -> None:
        raise NotImplementedError
