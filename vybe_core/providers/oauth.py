from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from hashlib import sha256
from secrets import token_urlsafe
from base64 import urlsafe_b64encode
from uuid import UUID, uuid4


def _pkce_challenge(verifier: str) -> str:
    digest = sha256(verifier.encode("ascii")).digest()
    return urlsafe_b64encode(digest).decode("ascii").rstrip("=")


@dataclass(frozen=True, slots=True)
class OAuthAuthorizationRequest:
    application_id: UUID
    person_id: UUID
    provider: str
    redirect_uri: str
    scopes: tuple[str, ...]
    state: str
    code_verifier: str
    code_challenge: str
    created_at: datetime
    expires_at: datetime
    connection_id: UUID = field(default_factory=uuid4)

    def __post_init__(self) -> None:
        if not self.provider.strip():
            raise ValueError("provider must not be empty")
        if not self.redirect_uri.strip():
            raise ValueError("redirect_uri must not be empty")
        if self.created_at.tzinfo is None or self.expires_at.tzinfo is None:
            raise ValueError("OAuth timestamps must be timezone-aware")
        if self.expires_at <= self.created_at:
            raise ValueError("expires_at must be after created_at")
        if not self.state or not self.code_verifier or not self.code_challenge:
            raise ValueError("OAuth state and PKCE fields must not be empty")


def create_authorization_request(
    *,
    application_id: UUID,
    person_id: UUID,
    provider: str,
    redirect_uri: str,
    scopes: tuple[str, ...],
    created_at: datetime,
    expires_at: datetime,
) -> OAuthAuthorizationRequest:
    verifier = token_urlsafe(48)
    return OAuthAuthorizationRequest(
        application_id=application_id,
        person_id=person_id,
        provider=provider,
        redirect_uri=redirect_uri,
        scopes=scopes,
        state=token_urlsafe(32),
        code_verifier=verifier,
        code_challenge=_pkce_challenge(verifier),
        created_at=created_at,
        expires_at=expires_at,
    )


def validate_callback_state(
    *,
    request: OAuthAuthorizationRequest,
    returned_state: str,
    now: datetime,
) -> None:
    from hmac import compare_digest

    if now.tzinfo is None:
        raise ValueError("now must be timezone-aware")
    if now >= request.expires_at:
        raise ValueError("OAuth authorization request expired")
    if not compare_digest(request.state, returned_state):
        raise ValueError("OAuth state mismatch")
