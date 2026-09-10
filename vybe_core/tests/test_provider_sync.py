from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

import pytest

from vybe_core.ingestion.checkpoint import CheckpointStore, SyncCheckpoint
from vybe_core.ingestion.executor import ProviderIngestionExecutor
from vybe_core.models.evidence import Evidence, EvidenceProvenance, EvidenceSource, SourceType
from vybe_core.providers.contracts import DeliveryMode, EvidenceProvider, ProviderCapabilities, SyncWindow
from vybe_core.providers.registry import ProviderRegistry
from vybe_core.providers.sync import ProviderBatch, ProviderSyncRunner
from vybe_core.storage.contracts import EvidenceQuery, EvidenceStore


NOW = datetime(2026, 9, 10, 18, 0, tzinfo=timezone.utc)


def evidence(value: int, at: datetime) -> Evidence:
    return Evidence(
        metric="heart_rate",
        value=value,
        unit="bpm",
        recorded_at=at,
        source=EvidenceSource(source_type=SourceType.CLOUD_PROVIDER, provider="fake"),
        provenance=EvidenceProvenance(
            ingested_at=NOW,
            processor="fake_adapter",
            processing_version="1.0.0",
        ),
    )


class FakeProvider(EvidenceProvider):
    def __init__(self, batches: dict[str | None, ProviderBatch]) -> None:
        self.batches = batches
        self.calls: list[tuple[str, str | None]] = []

    @property
    def provider_id(self) -> str:
        return "fake"

    @property
    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            delivery_modes=frozenset({DeliveryMode.REST_PULL}),
            supports_historical_sync=True,
            max_historical_days=30,
        )

    async def collect(self, subject_id: str, stream: str, window: SyncWindow):
        if False:
            yield evidence(0, NOW)

    async def collect_batch(
        self,
        *,
        subject_id: str,
        stream: str,
        window: SyncWindow,
        cursor: str | None,
    ) -> ProviderBatch:
        self.calls.append((stream, cursor))
        return self.batches[cursor]


class MemoryEvidenceStore(EvidenceStore):
    def __init__(self) -> None:
        self.items: list[tuple[UUID, Evidence]] = []

    async def append(self, person_id: UUID, item: Evidence) -> None:
        self.items.append((person_id, item))

    async def append_many(self, person_id: UUID, items) -> None:
        self.items.extend((person_id, item) for item in items)

    async def query(self, request: EvidenceQuery) -> tuple[Evidence, ...]:
        return tuple(item for person, item in self.items if person == request.person_id)

    async def get(self, person_id: UUID, evidence_id: UUID) -> Evidence | None:
        return next((item for person, item in self.items if person == person_id and item.id == evidence_id), None)


class MemoryCheckpointStore(CheckpointStore):
    def __init__(self) -> None:
        self.values: dict[tuple[UUID, str, str], SyncCheckpoint] = {}

    async def get(self, person_id: UUID, provider: str, stream: str) -> SyncCheckpoint | None:
        return self.values.get((person_id, provider, stream))

    async def put(self, checkpoint: SyncCheckpoint) -> None:
        self.values[(checkpoint.person_id, checkpoint.provider, checkpoint.stream)] = checkpoint


class MemoryIdempotencyStore:
    def __init__(self) -> None:
        self.keys: set[str] = set()

    async def seen(self, key: str) -> bool:
        return key in self.keys

    async def mark_seen(self, key: str) -> None:
        self.keys.add(key)


def build_runner(provider: FakeProvider, *, max_batches: int = 100):
    registry = ProviderRegistry()
    registry.register(provider)
    evidence_store = MemoryEvidenceStore()
    checkpoints = MemoryCheckpointStore()
    idempotency = MemoryIdempotencyStore()
    executor = ProviderIngestionExecutor(
        evidence_store=evidence_store,
        checkpoint_store=checkpoints,
        idempotency_store=idempotency,
    )
    runner = ProviderSyncRunner(
        registry=registry,
        checkpoint_store=checkpoints,
        executor=executor,
        max_batches_per_run=max_batches,
    )
    return runner, evidence_store, checkpoints


@pytest.mark.asyncio
async def test_multi_page_sync_advances_opaque_cursor_after_each_batch() -> None:
    provider = FakeProvider(
        {
            None: ProviderBatch((evidence(70, NOW - timedelta(minutes=2)),), "p2", True, "batch-1"),
            "p2": ProviderBatch((evidence(72, NOW - timedelta(minutes=1)),), "p3", False, "batch-2"),
        }
    )
    runner, store, checkpoints = build_runner(provider)
    person_id = uuid4()

    result = await runner.run(
        person_id=person_id,
        subject_id="subject-1",
        provider_id="fake",
        stream="heart_rate",
        window=SyncWindow(NOW - timedelta(days=1), NOW),
        observed_at=NOW,
    )

    assert result.completed is True
    assert result.batches == 2
    assert result.persisted == 2
    assert provider.calls == [("heart_rate", None), ("heart_rate", "p2")]
    checkpoint = await checkpoints.get(person_id, "fake", "heart_rate")
    assert checkpoint is not None
    assert checkpoint.cursor == "p3"
    assert len(store.items) == 2


@pytest.mark.asyncio
async def test_existing_checkpoint_is_passed_back_to_provider_opaque() -> None:
    provider = FakeProvider({"resume-token": ProviderBatch((), "done", False, "batch-resume")})
    runner, _, checkpoints = build_runner(provider)
    person_id = uuid4()
    await checkpoints.put(SyncCheckpoint(person_id, "fake", "heart_rate", "resume-token", NOW))

    await runner.run(
        person_id=person_id,
        subject_id="subject-1",
        provider_id="fake",
        stream="heart_rate",
        window=SyncWindow(NOW - timedelta(days=1), NOW),
        observed_at=NOW,
    )

    assert provider.calls == [("heart_rate", "resume-token")]


@pytest.mark.asyncio
async def test_has_more_requires_next_cursor() -> None:
    provider = FakeProvider({None: ProviderBatch((), None, True, "broken")})
    runner, _, _ = build_runner(provider)

    with pytest.raises(RuntimeError, match="has_more=True"):
        await runner.run(
            person_id=uuid4(),
            subject_id="subject-1",
            provider_id="fake",
            stream="heart_rate",
            window=SyncWindow(NOW - timedelta(days=1), NOW),
            observed_at=NOW,
        )


@pytest.mark.asyncio
async def test_max_batch_limit_stops_unbounded_provider_loop() -> None:
    provider = FakeProvider(
        {
            None: ProviderBatch((), "a", True, "1"),
            "a": ProviderBatch((), "b", True, "2"),
            "b": ProviderBatch((), "c", True, "3"),
        }
    )
    runner, _, _ = build_runner(provider, max_batches=2)

    result = await runner.run(
        person_id=uuid4(),
        subject_id="subject-1",
        provider_id="fake",
        stream="heart_rate",
        window=SyncWindow(NOW - timedelta(days=1), NOW),
        observed_at=NOW,
    )

    assert result.completed is False
    assert result.batches == 2
    assert result.final_cursor == "b"


@pytest.mark.asyncio
async def test_registry_enforces_provider_historical_window_limit() -> None:
    provider = FakeProvider({})
    runner, _, _ = build_runner(provider)

    with pytest.raises(ValueError, match="at most 30"):
        await runner.run(
            person_id=uuid4(),
            subject_id="subject-1",
            provider_id="fake",
            stream="heart_rate",
            window=SyncWindow(NOW - timedelta(days=31), NOW),
            observed_at=NOW,
        )
