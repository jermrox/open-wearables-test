from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID, uuid4

import pytest

from vybe_core.ingestion.checkpoint import CheckpointStore, SyncCheckpoint
from vybe_core.ingestion.executor import IngestionExecutionError, ProviderIngestionExecutor, ProviderProgress
from vybe_core.models.evidence import Evidence, EvidenceProvenance, EvidenceSource, SourceType
from vybe_core.storage.contracts import EvidenceQuery, EvidenceStore


NOW = datetime(2026, 9, 10, 18, 0, tzinfo=timezone.utc)


def sample_evidence() -> Evidence:
    return Evidence(
        metric="heart_rate",
        value=72,
        unit="bpm",
        recorded_at=NOW,
        source=EvidenceSource(source_type=SourceType.CLOUD_PROVIDER, provider="example"),
        provenance=EvidenceProvenance(
            ingested_at=NOW,
            processor="example_adapter",
            processing_version="1.0.0",
        ),
    )


class MemoryEvidenceStore(EvidenceStore):
    def __init__(self, *, fail: bool = False) -> None:
        self.items: list[tuple[UUID, Evidence]] = []
        self.fail = fail

    async def append(self, person_id: UUID, evidence: Evidence) -> None:
        if self.fail:
            raise RuntimeError("storage down")
        self.items.append((person_id, evidence))

    async def append_many(self, person_id: UUID, evidence) -> None:
        if self.fail:
            raise RuntimeError("storage down")
        self.items.extend((person_id, item) for item in evidence)

    async def query(self, request: EvidenceQuery) -> tuple[Evidence, ...]:
        return tuple(item for person, item in self.items if person == request.person_id)

    async def get(self, person_id: UUID, evidence_id: UUID) -> Evidence | None:
        for person, item in self.items:
            if person == person_id and item.id == evidence_id:
                return item
        return None


class MemoryCheckpointStore(CheckpointStore):
    def __init__(self, *, fail: bool = False) -> None:
        self.value: SyncCheckpoint | None = None
        self.fail = fail

    async def get(self, person_id: UUID, provider: str, stream: str) -> SyncCheckpoint | None:
        return self.value

    async def put(self, checkpoint: SyncCheckpoint) -> None:
        if self.fail:
            raise RuntimeError("checkpoint down")
        self.value = checkpoint


class MemoryIdempotencyStore:
    def __init__(self) -> None:
        self.keys: set[str] = set()

    async def seen(self, key: str) -> bool:
        return key in self.keys

    async def mark_seen(self, key: str) -> None:
        self.keys.add(key)


@pytest.mark.asyncio
async def test_success_persists_marks_seen_then_advances_checkpoint() -> None:
    person_id = uuid4()
    evidence_store = MemoryEvidenceStore()
    checkpoint_store = MemoryCheckpointStore()
    idempotency = MemoryIdempotencyStore()
    executor = ProviderIngestionExecutor(
        evidence_store=evidence_store,
        checkpoint_store=checkpoint_store,
        idempotency_store=idempotency,
    )

    result = await executor.execute(
        person_id=person_id,
        provider="example",
        evidence=[sample_evidence()],
        idempotency_key="batch-1",
        progress=ProviderProgress(stream="heart_rate", cursor="next-1", observed_at=NOW),
    )

    assert result.persisted_count == 1
    assert result.checkpoint_advanced is True
    assert "batch-1" in idempotency.keys
    assert checkpoint_store.value is not None
    assert checkpoint_store.value.cursor == "next-1"


@pytest.mark.asyncio
async def test_persistence_failure_does_not_mark_seen_or_advance_checkpoint() -> None:
    person_id = uuid4()
    evidence_store = MemoryEvidenceStore(fail=True)
    checkpoint_store = MemoryCheckpointStore()
    idempotency = MemoryIdempotencyStore()
    executor = ProviderIngestionExecutor(
        evidence_store=evidence_store,
        checkpoint_store=checkpoint_store,
        idempotency_store=idempotency,
    )

    with pytest.raises(IngestionExecutionError):
        await executor.execute(
            person_id=person_id,
            provider="example",
            evidence=[sample_evidence()],
            idempotency_key="batch-2",
            progress=ProviderProgress(stream="heart_rate", cursor="next-2", observed_at=NOW),
        )

    assert "batch-2" not in idempotency.keys
    assert checkpoint_store.value is None


@pytest.mark.asyncio
async def test_checkpoint_failure_marks_batch_seen_after_evidence_commit() -> None:
    person_id = uuid4()
    evidence_store = MemoryEvidenceStore()
    checkpoint_store = MemoryCheckpointStore(fail=True)
    idempotency = MemoryIdempotencyStore()
    executor = ProviderIngestionExecutor(
        evidence_store=evidence_store,
        checkpoint_store=checkpoint_store,
        idempotency_store=idempotency,
    )

    with pytest.raises(IngestionExecutionError):
        await executor.execute(
            person_id=person_id,
            provider="example",
            evidence=[sample_evidence()],
            idempotency_key="batch-3",
            progress=ProviderProgress(stream="heart_rate", cursor="next-3", observed_at=NOW),
        )

    assert len(evidence_store.items) == 1
    assert "batch-3" in idempotency.keys
    assert checkpoint_store.value is None


@pytest.mark.asyncio
async def test_duplicate_batch_repairs_checkpoint_without_reprocessing() -> None:
    person_id = uuid4()
    evidence_store = MemoryEvidenceStore()
    checkpoint_store = MemoryCheckpointStore()
    idempotency = MemoryIdempotencyStore()
    idempotency.keys.add("batch-4")
    executor = ProviderIngestionExecutor(
        evidence_store=evidence_store,
        checkpoint_store=checkpoint_store,
        idempotency_store=idempotency,
    )

    result = await executor.execute(
        person_id=person_id,
        provider="example",
        evidence=[sample_evidence()],
        idempotency_key="batch-4",
        progress=ProviderProgress(stream="heart_rate", cursor="next-4", observed_at=NOW),
    )

    assert result.duplicate is True
    assert result.checkpoint_advanced is True
    assert evidence_store.items == []
    assert checkpoint_store.value is not None
    assert checkpoint_store.value.cursor == "next-4"
