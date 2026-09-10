from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import datetime
from hashlib import sha256
from hmac import compare_digest
from secrets import token_urlsafe
from typing import Protocol
from uuid import UUID, uuid4

from vybe_core.providers.connections import TokenVault
from vybe_core.providers.oauth import _pkce_challenge


def _digest_secret(value: str) -> str:
    return sha256(value.encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class OAuthAuthorizationState:
    application_id: UUID
    person_id: UUID
    provider: str
    redirect_uri: str
    scopes: tuple[str, ...]
    state_digest: str
    verifier_reference: str
    code_challenge: str
    created_at: datetime
    expires_at: datetime
    consumed_at: datetime | None = None
    id: UUID = field(default_factory=uuid4)

    def __post_init__(self) -> None:
        if not self.provider.strip():
            raise ValueError("provider must not be empty")
        if not self.redirect_uri.strip():
            raise ValueError("redirect_uri must not be empty")
        if self.created_at.tzinfo is None or self.expires_at.tzinfo is None:
            raise ValueError("OAuth timestamps must be timezone-aware")
        if self.expires_at <= self.created_at:
            raise ValueError("expires_at must be after created_at")
        if self.consumed_at is not None and self.consumed_at.tzinfo is None:
            raise ValueError("consumed_at must be timezone-aware")
        if self.consumed_at is not None and self.consumed_at < self.created_at:
            raise ValueError("consumed_at cannot predate creation")
        if not self.state_digest or not self.verifier_reference or not self.code_challenge:
            raise ValueError("OAuth security fields must not be empty")


@dataclass(frozen=True, slots=True)
class OAuthLaunch:
    state: OAuthAuthorizationState
    returned_state_token: str


class OAuthStateStore(Protocol):
    async def put(self, state: OAuthAuthorizationState) -> None: ...

    async def get(self, state_id: UUID) -> OAuthAuthorizationState | None: ...

    async def consume(self, state_id: UUID, *, consumed_at: datetime) -> OAuthAuthorizationState: ...


def create_oauth_launch(
    *,
    application_id: UUID,
    person_id: UUID,
    provider: str,
    redirect_uri: str,
    scopes: tuple[str, ...],
    created_at: datetime,
    expires_at: datetime,
    token_vault: TokenVault,
) -> OAuthLaunch:
    verifier = token_urlsafe(48)
    returned_state = token_urlsafe(32)
    verifier_reference = token_vault.put(
        namespace=f"oauth-pkce/{application_id}/{person_id}/{provider}",
        secret=verifier,
    )
    state = OAuthAuthorizationState(
        application_id=application_id,
        person_id=person_id,
        provider=provider,
        redirect_uri=redirect_uri,
        scopes=scopes,
        state_digest=_digest_secret(returned_state),
        verifier_reference=verifier_reference,
        code_challenge=_pkce_challenge(verifier),
        created_at=created_at,
        expires_at=expires_at,
    )
    return OAuthLaunch(state=state, returned_state_token=returned_state)


def validate_returned_state(
    *,
    state: OAuthAuthorizationState,
    returned_state_token: str,
    now: datetime,
) -> None:
    if now.tzinfo is None:
        raise ValueError("now must be timezone-aware")
    if state.consumed_at is not None:
        raise ValueError("OAuth authorization state already consumed")
    if now >= state.expires_at:
        raise ValueError("OAuth authorization state expired")
    if not compare_digest(state.state_digest, _digest_secret(returned_state_token)):
        raise ValueError("OAuth state mismatch")


def consume_state(state: OAuthAuthorizationState, *, consumed_at: datetime) -> OAuthAuthorizationState:
    if consumed_at.tzinfo is None:
        raise ValueError("consumed_at must be timezone-aware")
    if state.consumed_at is not None:
        raise ValueError("OAuth authorization state already consumed")
    if consumed_at >= state.expires_at:
        raise ValueError("OAuth authorization state expired")
    return replace(state, consumed_at=consumed_at)


def retrieve_pkce_verifier(state: OAuthAuthorizationState, *, token_vault: TokenVault) -> str:
    return token_vault.get(state.verifier_reference)
