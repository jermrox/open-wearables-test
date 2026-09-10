from __future__ import annotations

import os
from datetime import datetime, timezone
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import create_async_engine

from vybe_core.ingestion.checkpoint import SyncCheckpoint
from vybe_core.models.evidence import (
    Evidence,
    EvidenceProvenance,
    EvidenceQuality,
    EvidenceSource,
    SourceType,
)
from vybe_core.storage.contracts import EvidenceQuery
from vybe_core.storage.postgres import PostgresEvidenceStore, metadata
from vybe_core.storage.postgres_state import PostgresCheckpointStore, PostgresIdempotencyStore


DATABASE_URL = os.environ.get(
    "VYBE_TEST_DATABASE_URL",
    "postgresql+psycopg://postgres:postgres@127.0.0.1:5432/vybe_test",
)
NOW = datetime(2026, 9, 10, 18, 0, tzinfo=timezone.utc)


@pytest_asyncio.fixture
async def engine():
    engine = create_async_engine(DATABASE_URL)
    async with engine.begin() as connection:
        await connection.run_sync(metadata.drop_all)
        await connection.run_sync(metadata.create_all)
    try:
        yield engine
    finally:
        async with engine.begin() as connection:
            await connection.run_sync(metadata.drop_all)
        await engine.dispose()


@pytest.mark.asyncio
async def test_evidence_round_trip_preserves_provenance_and_quality(engine) -> None:
    store = PostgresEvidenceStore(engine)
    person_id = uuid4()
    parent_id = uuid4()
    item = Evidence(
        metric="hrv_rmssd",
        value=48.5,
        unit="ms",
        recorded_at=NOW,
        source=EvidenceSource(
            source_type=SourceType.CLOUD_PROVIDER,
            provider="example",
            device_id="device-1",
            sensor="ppg",
            source_record_id="source-123",
            firmware_version="2.1.0",
        ),
        quality=EvidenceQuality(signal_quality=0.91, confidence=0.88, completeness=1.0, flags=("resting",)),
        provenance=EvidenceProvenance(
            ingested_at=NOW,
            processor="example_adapter",
            processing_version="1.2.3",
            raw_sha256="a" * 64,
            parent_evidence_ids=(parent_id,),
        ),
        metadata={"sample_count": 120},
    )

    await store.append(person_id, item)
    loaded = await store.get(person_id, item.id)

    assert loaded == item


@pytest.mark.asyncio
async def test_query_is_person_scoped_and_metric_filtered(engine) -> None:
    store = PostgresEvidenceStore(engine)
    person_a = uuid4()
    person_b = uuid4()

    def item(metric: str, value: int) -> Evidence:
        return Evidence(
            metric=metric,
            value=value,
            unit="bpm" if metric == "heart_rate" else "count",
            recorded_at=NOW,
            source=EvidenceSource(source_type=SourceType.CLOUD_PROVIDER, provider="example"),
            provenance=EvidenceProvenance(
                ingested_at=NOW,
                processor="example_adapter",
                processing_version="1.0.0",
            ),
        )

    await store.append_many(person_a, (item("heart_rate", 70), item("steps", 1000)))
    await store.append(person_b, item("heart_rate", 99))

    results = await store.query(EvidenceQuery(person_id=person_a, metrics=("heart_rate",)))
    assert len(results) == 1
    assert results[0].value == 70


@pytest.mark.asyncio
async def test_append_many_is_atomic_on_primary_key_conflict(engine) -> None:
    store = PostgresEvidenceStore(engine)
    person_id = uuid4()
    shared_id = uuid4()

    def item(value: int) -> Evidence:
        return Evidence(
            id=shared_id,
            metric="heart_rate",
            value=value,
            unit="bpm",
            recorded_at=NOW,
            source=EvidenceSource(source_type=SourceType.CLOUD_PROVIDER, provider="example"),
            provenance=EvidenceProvenance(
                ingested_at=NOW,
                processor="example_adapter",
                processing_version="1.0.0",
            ),
        )

    with pytest.raises(Exception):
        await store.append_many(person_id, (item(70), item(71)))

    results = await store.query(EvidenceQuery(person_id=person_id))
    assert results == ()


@pytest.mark.asyncio
async def test_checkpoint_upsert_and_idempotency_survive_new_store_instances(engine) -> None:
    person_id = uuid4()
    checkpoints = PostgresCheckpointStore(engine)
    replay = PostgresIdempotencyStore(engine)

    await checkpoints.put(SyncCheckpoint(person_id, "example", "sleep", "cursor-1", NOW))
    await checkpoints.put(SyncCheckpoint(person_id, "example", "sleep", "cursor-2", NOW))
    await replay.mark_seen("b" * 64)

    reloaded_checkpoint = await PostgresCheckpointStore(engine).get(person_id, "example", "sleep")
    assert reloaded_checkpoint is not None
    assert reloaded_checkpoint.cursor == "cursor-2"
    assert await PostgresIdempotencyStore(engine).seen("b" * 64) is True
