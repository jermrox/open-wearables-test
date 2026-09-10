from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID

from vybe_core.ingestion.checkpoint import CheckpointStore
from vybe_core.ingestion.executor import BatchExecutionResult, ProviderIngestionExecutor, ProviderProgress
from vybe_core.ingestion.idempotency import IdempotencyKeyBuilder
from vybe_core.models.evidence import Evidence
from vybe_core.providers.contracts import DeliveryMode, SyncWindow
from vybe_core.providers.registry import ProviderRegistry


@dataclass(frozen=True, slots=True)
class ProviderBatch:
    evidence: tuple[Evidence, ...]
    next_cursor: str | None
    has_more: bool
    source_batch_id: str | None = None


class IncrementalEvidenceProvider(Protocol):
    @property
    def provider_id(self) -> str: ...

    async def collect_batch(
        self,
        *,
        subject_id: str,
        stream: str,
        window: SyncWindow,
        cursor: str | None,
    ) -> ProviderBatch: ...


@dataclass(frozen=True, slots=True)
class SyncRunResult:
    provider: str
    stream: str
    batches: int
    persisted: int
    rejected: int
    final_cursor: str | None
    completed: bool


class ProviderSyncRunner:
    """Runs incremental REST sync using stream-explicit opaque cursors."""

    def __init__(
        self,
        *,
        registry: ProviderRegistry,
        checkpoint_store: CheckpointStore,
        executor: ProviderIngestionExecutor,
        idempotency_keys: IdempotencyKeyBuilder | None = None,
        max_batches_per_run: int = 100,
    ) -> None:
        if max_batches_per_run <= 0:
            raise ValueError("max_batches_per_run must be positive")
        self._registry = registry
        self._checkpoint_store = checkpoint_store
        self._executor = executor
        self._idempotency_keys = idempotency_keys or IdempotencyKeyBuilder()
        self._max_batches_per_run = max_batches_per_run

    async def run(
        self,
        *,
        person_id: UUID,
        subject_id: str,
        provider_id: str,
        stream: str,
        window: SyncWindow,
        observed_at: datetime,
    ) -> SyncRunResult:
        if observed_at.tzinfo is None:
            raise ValueError("observed_at must be timezone-aware")
        if not stream.strip():
            raise ValueError("stream must not be empty")

        self._registry.require_delivery_mode(provider_id, DeliveryMode.REST_PULL, stream=stream)
        self._registry.validate_window(provider_id, window, stream=stream)
        provider = self._registry.get(provider_id)
        collect_batch = getattr(provider, "collect_batch", None)
        if collect_batch is None:
            raise TypeError(f"provider {provider.provider_id} does not support incremental batch sync")

        checkpoint = await self._checkpoint_store.get(person_id, provider.provider_id, stream)
        cursor = checkpoint.cursor if checkpoint is not None else None

        total_persisted = 0
        total_rejected = 0
        batch_count = 0
        completed = False

        while batch_count < self._max_batches_per_run:
            batch: ProviderBatch = await collect_batch(
                subject_id=subject_id,
                stream=stream,
                window=window,
                cursor=cursor,
            )
            batch_count += 1

            batch_key_material = batch.source_batch_id or (
                f"{person_id}|{provider.provider_id}|{stream}|{cursor or 'START'}|{batch.next_cursor or 'END'}"
            )
            idempotency_key = self._idempotency_keys.hash_material(batch_key_material)

            result: BatchExecutionResult = await self._executor.execute(
                person_id=person_id,
                provider=provider.provider_id,
                evidence=batch.evidence,
                idempotency_key=idempotency_key,
                progress=ProviderProgress(
                    stream=stream,
                    cursor=batch.next_cursor,
                    observed_at=observed_at,
                ),
            )
            total_persisted += result.persisted_count
            total_rejected += result.rejected_count
            cursor = batch.next_cursor

            if not batch.has_more:
                completed = True
                break
            if batch.next_cursor is None:
                raise RuntimeError(
                    f"provider {provider.provider_id} returned has_more=True without a next_cursor"
                )

        return SyncRunResult(
            provider=provider.provider_id,
            stream=stream,
            batches=batch_count,
            persisted=total_persisted,
            rejected=total_rejected,
            final_cursor=cursor,
            completed=completed,
        )
