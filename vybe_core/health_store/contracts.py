from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID

from vybe_core.models.evidence import Evidence


@dataclass(frozen=True, slots=True)
class HealthStoreWriteResult:
    metric: str
    evidence_id: UUID
    written_at: datetime
    store_record_id: str | None = None

    def __post_init__(self) -> None:
        if not self.metric.strip():
            raise ValueError("metric must not be empty")
        if self.written_at.tzinfo is None:
            raise ValueError("written_at must be timezone-aware")


class HealthStoreBridge(Protocol):
    """Local/mobile health repository boundary.

    Examples include Apple HealthKit and Android Health Connect. This contract is
    intentionally limited to health-data authorization, reads, and supported
    writes. It does not expose clinical ordering, prescriptions, physician
    review, payment, fulfillment, logistics, or diagnostic ordering workflows.
    """

    @property
    def store_id(self) -> str: ...

    async def read_evidence(
        self,
        *,
        person_id: UUID,
        metrics: tuple[str, ...],
        start: datetime,
        end: datetime,
    ) -> tuple[Evidence, ...]: ...

    async def write_evidence(
        self,
        *,
        person_id: UUID,
        evidence: Evidence,
    ) -> HealthStoreWriteResult: ...


class HealthStoreCapabilityError(RuntimeError):
    pass


def reject_clinical_ordering(store_id: str) -> None:
    """Fail closed when code attempts to use a health store as an ordering API."""

    raise HealthStoreCapabilityError(
        f"{store_id} is a health-data repository and cannot place clinical or laboratory orders"
    )
