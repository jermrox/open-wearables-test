from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import create_async_engine

from vybe_core.providers.oauth_state import create_oauth_launch, validate_returned_state
from vybe_core.storage.postgres import metadata
from vybe_core.storage.postgres_oauth import PostgresOAuthStateStore


DATABASE_URL = os.environ.get(
    "VYBE_TEST_DATABASE_URL",
    "postgresql+psycopg://postgres:postgres@127.0.0.1:5432/vybe_test",
)
NOW = datetime(2026, 9, 10, 18, 0, tzinfo=timezone.utc)


class MemoryVault:
    def __init__(self) -> None:
        self.values: dict[str, str] = {}

    def put(self, *, namespace: str, secret: str) -> str:
        reference = f"vault://{namespace}/{len(self.values) + 1}"
        self.values[reference] = secret
        return reference

    def get(self, reference: str) -> str:
        return self.values[reference]

    def delete(self, reference: str) -> None:
        del self.values[reference]


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
async def test_oauth_state_round_trip_and_atomic_consume(engine) -> None:
    vault = MemoryVault()
    launch = create_oauth_launch(
        application_id=uuid4(),
        person_id=uuid4(),
        provider="oura",
        redirect_uri="https://example.com/oauth/callback",
        scopes=("daily", "sleep"),
        created_at=NOW,
        expires_at=NOW + timedelta(minutes=10),
        token_vault=vault,
    )
    store = PostgresOAuthStateStore(engine)

    await store.put(launch.state)
    loaded = await store.get(launch.state.id)
    assert loaded == launch.state
    assert loaded is not None
    validate_returned_state(
        state=loaded,
        returned_state_token=launch.returned_state_token,
        now=NOW + timedelta(minutes=1),
    )

    consumed = await store.consume(loaded.id, consumed_at=NOW + timedelta(minutes=1))
    assert consumed.consumed_at == NOW + timedelta(minutes=1)

    with pytest.raises(ValueError, match="expired or already consumed"):
        await store.consume(loaded.id, consumed_at=NOW + timedelta(minutes=2))
