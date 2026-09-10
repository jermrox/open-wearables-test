from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

import pytest

from vybe_core.providers.connections import ConnectionStatus, ProviderConnection
from vybe_core.providers.tokens import (
    ProviderReauthorizationRequired,
    ProviderTokenSet,
    attach_token_set,
    ensure_fresh_token,
    load_token_set,
    token_needs_refresh,
)


NOW = datetime(2026, 9, 10, 18, 0, tzinfo=timezone.utc)


class MemoryVault:
    def __init__(self) -> None:
        self.values: dict[str, str] = {}
        self.deleted: list[str] = []

    def put(self, *, namespace: str, secret: str) -> str:
        reference = f"vault://{namespace}/{len(self.values) + 1}"
        self.values[reference] = secret
        return reference

    def get(self, reference: str) -> str:
        return self.values[reference]

    def delete(self, reference: str) -> None:
        self.deleted.append(reference)
        self.values.pop(reference, None)


class MemoryConnectionStore:
    def __init__(self, *, fail: bool = False) -> None:
        self.values: dict[UUID, ProviderConnection] = {}
        self.fail = fail

    async def put(self, connection: ProviderConnection) -> None:
        if self.fail:
            raise RuntimeError("db down")
        self.values[connection.id] = connection

    async def get(self, connection_id: UUID) -> ProviderConnection | None:
        return self.values.get(connection_id)

    async def get_for_person_provider(self, *, application_id: UUID, person_id: UUID, provider: str):
        return next(
            (
                value
                for value in self.values.values()
                if value.application_id == application_id
                and value.person_id == person_id
                and value.provider == provider
            ),
            None,
        )

    async def list_for_person(self, *, application_id: UUID, person_id: UUID):
        return tuple(
            value
            for value in self.values.values()
            if value.application_id == application_id and value.person_id == person_id
        )


class RefreshClient:
    def __init__(self, result: ProviderTokenSet | Exception) -> None:
        self.result = result
        self.seen_refresh_token: str | None = None

    async def refresh(self, refresh_token: str) -> ProviderTokenSet:
        self.seen_refresh_token = refresh_token
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


def connection() -> ProviderConnection:
    return ProviderConnection(
        application_id=uuid4(),
        person_id=uuid4(),
        provider="oura",
        created_at=NOW - timedelta(days=1),
        status=ConnectionStatus.ACTIVE,
    )


def test_refresh_decision_uses_expiry_with_skew() -> None:
    token = ProviderTokenSet("access", refresh_token="refresh", expires_at=NOW + timedelta(minutes=4))
    assert token_needs_refresh(token, now=NOW, refresh_skew=timedelta(minutes=5)) is True
    assert token_needs_refresh(token, now=NOW, refresh_skew=timedelta(minutes=1)) is False


@pytest.mark.asyncio
async def test_attach_token_set_compensates_if_connection_write_fails() -> None:
    vault = MemoryVault()
    store = MemoryConnectionStore(fail=True)
    item = connection()

    with pytest.raises(RuntimeError, match="db down"):
        await attach_token_set(
            connection=item,
            tokens=ProviderTokenSet("access", refresh_token="refresh"),
            token_vault=vault,
            connection_store=store,
        )

    assert vault.values == {}
    assert len(vault.deleted) == 1


@pytest.mark.asyncio
async def test_expired_token_refreshes_and_rotates_vault_reference() -> None:
    vault = MemoryVault()
    store = MemoryConnectionStore()
    item = connection()
    original = await attach_token_set(
        connection=item,
        tokens=ProviderTokenSet("old-access", refresh_token="old-refresh", expires_at=NOW - timedelta(minutes=1)),
        token_vault=vault,
        connection_store=store,
    )
    old_reference = original.token_reference
    refresher = RefreshClient(
        ProviderTokenSet("new-access", refresh_token="new-refresh", expires_at=NOW + timedelta(hours=1))
    )

    updated, tokens = await ensure_fresh_token(
        connection=original,
        now=NOW,
        token_vault=vault,
        connection_store=store,
        refresh_client=refresher,
    )

    assert refresher.seen_refresh_token == "old-refresh"
    assert updated.token_reference != old_reference
    assert old_reference in vault.deleted
    assert tokens.access_token == "new-access"
    assert load_token_set(token_vault=vault, reference=updated.token_reference).refresh_token == "new-refresh"


@pytest.mark.asyncio
async def test_missing_refresh_token_marks_connection_reauth_required() -> None:
    vault = MemoryVault()
    store = MemoryConnectionStore()
    item = await attach_token_set(
        connection=connection(),
        tokens=ProviderTokenSet("access", expires_at=NOW - timedelta(minutes=1)),
        token_vault=vault,
        connection_store=store,
    )

    with pytest.raises(ProviderReauthorizationRequired):
        await ensure_fresh_token(
            connection=item,
            now=NOW,
            token_vault=vault,
            connection_store=store,
            refresh_client=RefreshClient(ProviderTokenSet("unused")),
        )

    assert store.values[item.id].status is ConnectionStatus.REAUTH_REQUIRED


@pytest.mark.asyncio
async def test_provider_refresh_rejection_marks_reauth_required() -> None:
    vault = MemoryVault()
    store = MemoryConnectionStore()
    item = await attach_token_set(
        connection=connection(),
        tokens=ProviderTokenSet("access", refresh_token="refresh", expires_at=NOW - timedelta(minutes=1)),
        token_vault=vault,
        connection_store=store,
    )

    with pytest.raises(ProviderReauthorizationRequired):
        await ensure_fresh_token(
            connection=item,
            now=NOW,
            token_vault=vault,
            connection_store=store,
            refresh_client=RefreshClient(ProviderReauthorizationRequired("invalid_grant")),
        )

    assert store.values[item.id].status is ConnectionStatus.REAUTH_REQUIRED
