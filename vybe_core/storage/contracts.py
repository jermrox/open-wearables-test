from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Iterable
from uuid import UUID

from vybe_core.models.evidence import Evidence


@dataclass(frozen=True, slots=True)
class EvidenceQuery:
    person_id: UUID
    metrics: tuple[str, ...] = ()
    start: datetime | None = None
    end: datetime | None = None
    limit: int | None = None

    def __post_init__(self) -> None:
        if self.start is not None and self.start.tzinfo is None:
            raise ValueError("start must be timezone-aware")
        if self.end is not None and self.end.tzinfo is None:
            raise ValueError("end must be timezone-aware")
        if self.start is not None and self.end is not None and self.start > self.end:
            raise ValueError("start must be <= end")
        if self.limit is not None and self.limit <= 0:
            raise ValueError("limit must be positive")


class EvidenceStore(ABC):
    """Persistence boundary for immutable evidence.

    Storage implementations may use PostgreSQL, SQLite, object storage, or another
    backend, but callers depend only on this contract. Evidence records are append-
    only; mutation of existing evidence is intentionally not part of the interface.

    `append_many` MUST be atomic from the caller's perspective: either every item
    in the supplied batch is committed or none are. Implementations must roll back
    partial writes before raising. Provider ingestion relies on this guarantee for
    replay safety and checkpoint correctness.
    """

    @abstractmethod
    async def append(self, person_id: UUID, evidence: Evidence) -> None:
        raise NotImplementedError

    @abstractmethod
    async def append_many(self, person_id: UUID, evidence: Iterable[Evidence]) -> None:
        """Atomically append a batch of immutable evidence."""
        raise NotImplementedError

    @abstractmethod
    async def query(self, request: EvidenceQuery) -> tuple[Evidence, ...]:
        raise NotImplementedError

    @abstractmethod
    async def get(self, person_id: UUID, evidence_id: UUID) -> Evidence | None:
        raise NotImplementedError
