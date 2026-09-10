from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import create_async_engine

from vybe_core.access.consent import ConsentGrant, revoke_consent
from vybe_core.access.policy import DataScope
from vybe_core.audit.events import AuditAction, AuditEvent
from vybe_core.storage.postgres import metadata
from vybe_core.storage.postgres_privacy import PostgresAuditStore, PostgresConsentStore


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
async def test_consent_round_trip_and_revocation_removes_active_access(engine) -> None:
    store = PostgresConsentStore(engine)
    application_id = uuid4()
    person_id = uuid4()
    consent = ConsentGrant(
        application_id=application_id,
        person_id=person_id,
        purpose="Wearable metrics and event history",
        scopes=frozenset({DataScope.METRICS_READ, DataScope.EVENTS_READ}),
        granted_at=NOW,
        expires_at=NOW + timedelta(days=30),
    )

    await store.put(consent)
    loaded = await store.get(consent.id)
    assert loaded == consent
    assert await store.active_for(person_id=person_id, application_id=application_id, now=NOW) == (consent,)

    revoked = revoke_consent(consent, revoked_at=NOW + timedelta(minutes=5))
    await store.put(revoked)
    assert await store.get(consent.id) == revoked
    assert await store.active_for(
        person_id=person_id,
        application_id=application_id,
        now=NOW + timedelta(minutes=6),
    ) == ()


@pytest.mark.asyncio
async def test_audit_events_are_append_only_and_person_scoped(engine) -> None:
    store = PostgresAuditStore(engine)
    application_id = uuid4()
    person_id = uuid4()
    other_person = uuid4()

    first = AuditEvent(
        action=AuditAction.DATA_READ,
        occurred_at=NOW,
        application_id=application_id,
        person_id=person_id,
        actor_id="credential:abc",
        resource_type="metric",
        resource_id="heart_rate",
        request_id="request-1",
        metadata={"scope": "metrics:read"},
    )
    second = AuditEvent(
        action=AuditAction.CONSENT_GRANTED,
        occurred_at=NOW + timedelta(seconds=1),
        application_id=application_id,
        person_id=person_id,
        resource_type="consent",
        resource_id="consent-1",
    )
    unrelated = AuditEvent(
        action=AuditAction.DATA_READ,
        occurred_at=NOW + timedelta(seconds=2),
        application_id=application_id,
        person_id=other_person,
    )

    await store.append(first)
    await store.append(second)
    await store.append(unrelated)

    events = await store.list_for_person(person_id=person_id, application_id=application_id)
    assert events == (second, first)
