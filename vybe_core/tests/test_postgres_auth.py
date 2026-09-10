from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import create_async_engine

from vybe_core.access.policy import DataScope
from vybe_core.auth.authenticate import authenticate_api_key
from vybe_core.auth.credentials import CredentialVerificationError, issue_credential, revoke_credential
from vybe_core.auth.models import Application, Organization
from vybe_core.storage.postgres import metadata
from vybe_core.storage.postgres_auth import PostgresAuthStore


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
async def test_issue_persist_authenticate_and_revoke_credential(engine) -> None:
    store = PostgresAuthStore(engine)
    organization = Organization(name="Example Health", created_at=NOW)
    application = Application(organization_id=organization.id, name="Coach App", created_at=NOW)
    credential, plaintext = issue_credential(
        application=application,
        created_at=NOW,
        scopes=frozenset({DataScope.METRICS_READ.value, DataScope.EVENTS_READ.value}),
        expires_at=NOW + timedelta(days=30),
    )

    await store.put_organization(organization)
    await store.put_application(application)
    await store.put_credential(credential)

    assert plaintext not in credential.secret_hash
    loaded_application = await store.get_application(application.id)
    assert loaded_application == application

    authenticated = await authenticate_api_key(
        presented_key=plaintext,
        now=NOW + timedelta(minutes=1),
        auth_store=store,
        required_scope=DataScope.METRICS_READ,
    )
    assert authenticated.application_id == application.id
    assert authenticated.credential_id == credential.id
    assert authenticated.grant.allows(DataScope.METRICS_READ)

    await store.put_credential(revoke_credential(credential))
    with pytest.raises(CredentialVerificationError, match="not active"):
        await authenticate_api_key(
            presented_key=plaintext,
            now=NOW + timedelta(minutes=2),
            auth_store=store,
        )


@pytest.mark.asyncio
async def test_wrong_secret_and_unknown_prefix_fail_without_scope_leak(engine) -> None:
    store = PostgresAuthStore(engine)
    organization = Organization(name="Example Health", created_at=NOW)
    application = Application(organization_id=organization.id, name="Coach App", created_at=NOW)
    credential, plaintext = issue_credential(
        application=application,
        created_at=NOW,
        scopes=frozenset({DataScope.METRICS_READ.value}),
    )
    await store.put_organization(organization)
    await store.put_application(application)
    await store.put_credential(credential)

    prefix = plaintext.split(".", 1)[0]
    with pytest.raises(CredentialVerificationError):
        await authenticate_api_key(
            presented_key=f"{prefix}.wrong-secret",
            now=NOW,
            auth_store=store,
        )

    with pytest.raises(CredentialVerificationError, match="invalid credential"):
        await authenticate_api_key(
            presented_key="vybe_live_unknown.secret",
            now=NOW,
            auth_store=store,
        )
