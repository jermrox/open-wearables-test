from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Iterable, Protocol
from uuid import UUID

from vybe_core.ingestion.checkpoint import CheckpointStore, SyncCheckpoint
from vybe_core.ingestion.idempotency import IdempotencyStore
from vybe_core.models.evidence import Evidence
from vybe_core.refinery.pipeline import EvidenceRefinery, RefineryResult
from vybe_core.storage.contracts import EvidenceStore


class IngestionExecutionError(RuntimeError):
    """Raised when an ingestion batch cannot be committed safely."""


@dataclass(frozen=True, slots=True)
class ProviderProgress:
    """Provider-owned progress metadata.

    Cursor semantics intentionally remain opaque to the core. A provider adapter
    may supply a timestamp, page token, opaque cursor, or None.
    """

    stream: str
    cursor: str | None
    observed_at: datetime

    def __post_init__(self) -> None:
        if not self.stream.strip():
            raise ValueError("stream must not be empty")
        if self.observed_at.tzinfo is None:
            raise ValueError("observed_at must be timezone-aware")


@dataclass(frozen=True, slots=True)
class BatchExecutionResult:
    duplicate: bool
    persisted_count: int
    rejected_count: int
    duplicate_group_count: int
    checkpoint_advanced: bool
    refinery: RefineryResult | None = None


class AsyncIdempotencyStore(Protocol):
    async def seen(self, key: str) -> bool: ...

    async def mark_seen(self, key: str) -> None: ...


class ProviderIngestionExecutor:
    """Coordinates safe ingestion without owning provider-specific semantics.

    Commit ordering is deliberate:
    1. Check replay/idempotency state.
    2. Run the deterministic refinery.
    3. Persist accepted immutable evidence.
    4. Mark the batch idempotency key as seen.
    5. Advance the provider checkpoint.

    If refinement or persistence fails, neither idempotency nor checkpoint state
    is advanced. This makes retries safe and avoids silently skipping source data.
    """

    def __init__(
        self,
        *,
        evidence_store: EvidenceStore,
        checkpoint_store: CheckpointStore,
        idempotency_store: AsyncIdempotencyStore,
        refinery: EvidenceRefinery | None = None,
    ) -> None:
        self._evidence_store = evidence_store
        self._checkpoint_store = checkpoint_store
        self._idempotency_store = idempotency_store
        self._refinery = refinery or EvidenceRefinery()

    async def execute(
        self,
        *,
        person_id: UUID,
        provider: str,
        evidence: Iterable[Evidence],
        idempotency_key: str,
        progress: ProviderProgress | None = None,
    ) -> BatchExecutionResult:
        if not provider.strip():
            raise ValueError("provider must not be empty")
        if not idempotency_key.strip():
            raise ValueError("idempotency_key must not be empty")

        if await self._idempotency_store.seen(idempotency_key):
            return BatchExecutionResult(
                duplicate=True,
                persisted_count=0,
                rejected_count=0,
                duplicate_group_count=0,
                checkpoint_advanced=False,
                refinery=None,
            )

        try:
            refinery_result = self._refinery.process(tuple(evidence))
            await self._evidence_store.append_many(person_id, refinery_result.accepted)
        except Exception as exc:
            raise IngestionExecutionError("ingestion batch failed before commit state advancement") from exc

        # A persisted batch is now replay-safe. Mark it before advancing progress;
        # if checkpoint persistence fails, retrying the same batch will not append
        # duplicate evidence. The checkpoint can then be repaired/retried separately.
        await self._idempotency_store.mark_seen(idempotency_key)

        checkpoint_advanced = False
        if progress is not None:
            checkpoint = SyncCheckpoint(
                person_id=person_id,
                provider=provider,
                stream=progress.stream,
                cursor=progress.cursor,
                updated_at=progress.observed_at,
            )
            try:
                await self._checkpoint_store.put(checkpoint)
            except Exception as exc:
                raise IngestionExecutionError(
                    "evidence persisted and idempotency committed, but checkpoint advancement failed"
                ) from exc
            checkpoint_advanced = True

        return BatchExecutionResult(
            duplicate=False,
            persisted_count=len(refinery_result.accepted),
            rejected_count=len(refinery_result.rejected),
            duplicate_group_count=len(refinery_result.duplicate_groups),
            checkpoint_advanced=checkpoint_advanced,
            refinery=refinery_result,
        )
