from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import create_async_engine

from vybe_core.providers.connections import ConnectionStatus, ProviderConnection
from vybe_core.storage.postgres import metadata
from vybe_core.storage.postgres_connections import PostgresProviderConnectionStore


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
async def test_provider_connection_round_trip_stores_only_token_reference(engine) -> None:
    store = PostgresProviderConnectionStore(engine)
    connection = ProviderConnection(
        application_id=uuid4(),
        person_id=uuid4(),
        provider="oura",
        created_at=NOW,
        status=ConnectionStatus.ACTIVE,
        external_user_id="provider-user-1",
        token_reference="vault://tokens/abc",
    )

    await store.put(connection)
    loaded = await store.get(connection.id)

    assert loaded == connection
    assert loaded is not None
    assert loaded.token_reference == "vault://tokens/abc"


@pytest.mark.asyncio
async def test_put_updates_same_application_person_provider_connection(engine) -> None:
    store = PostgresProviderConnectionStore(engine)
    application_id = uuid4()
    person_id = uuid4()

    original = ProviderConnection(
        application_id=application_id,
        person_id=person_id,
        provider="garmin",
        created_at=NOW,
        status=ConnectionStatus.PENDING,
    )
    updated = ProviderConnection(
        application_id=application_id,
        person_id=person_id,
        provider="garmin",
        created_at=NOW,
        status=ConnectionStatus.ACTIVE,
        token_reference="vault://tokens/new",
        last_synced_at=NOW + timedelta(minutes=5),
    )

    await store.put(original)
    await store.put(updated)

    loaded = await store.get_for_person_provider(
        application_id=application_id,
        person_id=person_id,
        provider="garmin",
    )
    assert loaded is not None
    assert loaded.id == updated.id
    assert loaded.status is ConnectionStatus.ACTIVE
    assert loaded.token_reference == "vault://tokens/new"

    listed = await store.list_for_person(application_id=application_id, person_id=person_id)
    assert len(listed) == 1
