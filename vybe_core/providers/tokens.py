from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timedelta
import json
from typing import Protocol

from vybe_core.providers.connections import ConnectionStatus, ProviderConnection, ProviderConnectionStore, TokenVault


class ProviderReauthorizationRequired(RuntimeError):
    """Provider rejected refresh credentials and the user must reconnect."""


@dataclass(frozen=True, slots=True)
class ProviderTokenSet:
    access_token: str
    refresh_token: str | None = None
    token_type: str = "Bearer"
    expires_at: datetime | None = None
    scopes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.access_token:
            raise ValueError("access_token must not be empty")
        if self.expires_at is not None and self.expires_at.tzinfo is None:
            raise ValueError("expires_at must be timezone-aware")


class TokenRefreshClient(Protocol):
    async def refresh(self, refresh_token: str) -> ProviderTokenSet: ...


def _serialize_token_set(tokens: ProviderTokenSet) -> str:
    return json.dumps(
        {
            "access_token": tokens.access_token,
            "refresh_token": tokens.refresh_token,
            "token_type": tokens.token_type,
            "expires_at": tokens.expires_at.isoformat() if tokens.expires_at is not None else None,
            "scopes": list(tokens.scopes),
        },
        separators=(",", ":"),
        sort_keys=True,
    )


def _deserialize_token_set(payload: str) -> ProviderTokenSet:
    data = json.loads(payload)
    expires_at = datetime.fromisoformat(data["expires_at"]) if data.get("expires_at") else None
    return ProviderTokenSet(
        access_token=data["access_token"],
        refresh_token=data.get("refresh_token"),
        token_type=data.get("token_type", "Bearer"),
        expires_at=expires_at,
        scopes=tuple(data.get("scopes") or ()),
    )


def store_token_set(
    *,
    token_vault: TokenVault,
    connection: ProviderConnection,
    tokens: ProviderTokenSet,
) -> str:
    return token_vault.put(
        namespace=f"provider-tokens/{connection.application_id}/{connection.person_id}/{connection.provider}",
        secret=_serialize_token_set(tokens),
    )


def load_token_set(*, token_vault: TokenVault, reference: str) -> ProviderTokenSet:
    return _deserialize_token_set(token_vault.get(reference))


def token_needs_refresh(
    tokens: ProviderTokenSet,
    *,
    now: datetime,
    refresh_skew: timedelta = timedelta(minutes=5),
) -> bool:
    if now.tzinfo is None:
        raise ValueError("now must be timezone-aware")
    if refresh_skew < timedelta(0):
        raise ValueError("refresh_skew must not be negative")
    if tokens.expires_at is None:
        return False
    return now + refresh_skew >= tokens.expires_at


async def attach_token_set(
    *,
    connection: ProviderConnection,
    tokens: ProviderTokenSet,
    token_vault: TokenVault,
    connection_store: ProviderConnectionStore,
) -> ProviderConnection:
    """Store a new token bundle and atomically switch the connection reference.

    The new secret is written first. If connection persistence fails, the newly
    created secret is deleted and the old reference remains authoritative.
    After a successful connection update, the old secret is deleted best-effort.
    """

    new_reference = store_token_set(token_vault=token_vault, connection=connection, tokens=tokens)
    old_reference = connection.token_reference
    updated = replace(
        connection,
        token_reference=new_reference,
        status=ConnectionStatus.ACTIVE,
    )

    try:
        await connection_store.put(updated)
    except Exception:
        token_vault.delete(new_reference)
        raise

    if old_reference is not None and old_reference != new_reference:
        try:
            token_vault.delete(old_reference)
        except Exception:
            # Secret cleanup failure must not roll back a connection that already
            # points to valid new credentials. Operational cleanup can retry later.
            pass

    return updated


async def ensure_fresh_token(
    *,
    connection: ProviderConnection,
    now: datetime,
    token_vault: TokenVault,
    connection_store: ProviderConnectionStore,
    refresh_client: TokenRefreshClient,
    refresh_skew: timedelta = timedelta(minutes=5),
) -> tuple[ProviderConnection, ProviderTokenSet]:
    if connection.status in {ConnectionStatus.REVOKED, ConnectionStatus.REAUTH_REQUIRED}:
        raise ProviderReauthorizationRequired(f"provider connection is {connection.status.value}")
    if connection.token_reference is None:
        reauth = replace(connection, status=ConnectionStatus.REAUTH_REQUIRED)
        await connection_store.put(reauth)
        raise ProviderReauthorizationRequired("provider connection has no token reference")

    tokens = load_token_set(token_vault=token_vault, reference=connection.token_reference)
    if not token_needs_refresh(tokens, now=now, refresh_skew=refresh_skew):
        return connection, tokens

    if not tokens.refresh_token:
        reauth = replace(connection, status=ConnectionStatus.REAUTH_REQUIRED)
        await connection_store.put(reauth)
        raise ProviderReauthorizationRequired("provider did not supply a refresh token")

    try:
        refreshed = await refresh_client.refresh(tokens.refresh_token)
    except ProviderReauthorizationRequired:
        reauth = replace(connection, status=ConnectionStatus.REAUTH_REQUIRED)
        await connection_store.put(reauth)
        raise

    updated = await attach_token_set(
        connection=connection,
        tokens=refreshed,
        token_vault=token_vault,
        connection_store=connection_store,
    )
    return updated, refreshed
