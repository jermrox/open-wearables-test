from __future__ import annotations

from dataclasses import replace
from datetime import datetime
from hashlib import sha256
from hmac import compare_digest
from secrets import token_urlsafe

from vybe_core.auth.models import ApiCredential, Application, CredentialStatus


class CredentialVerificationError(ValueError):
    pass


def _hash_secret(secret: str) -> str:
    return sha256(secret.encode("utf-8")).hexdigest()


def issue_credential(
    *,
    application: Application,
    created_at: datetime,
    scopes: frozenset[str],
    expires_at: datetime | None = None,
    prefix: str = "vybe_live",
) -> tuple[ApiCredential, str]:
    """Issue a credential and return the stored record plus one-time plaintext key.

    Only the hash belongs in persistence. The plaintext key is returned exactly
    once to the caller and must never be logged or persisted by this module.
    """
    if created_at.tzinfo is None:
        raise ValueError("created_at must be timezone-aware")
    if not scopes:
        raise ValueError("at least one scope is required")
    if not prefix.strip():
        raise ValueError("prefix must not be empty")

    secret = token_urlsafe(32)
    public_prefix = f"{prefix}_{token_urlsafe(6)}"
    plaintext = f"{public_prefix}.{secret}"
    credential = ApiCredential(
        application_id=application.id,
        key_prefix=public_prefix,
        secret_hash=_hash_secret(secret),
        scopes=scopes,
        created_at=created_at,
        expires_at=expires_at,
    )
    return credential, plaintext


def verify_credential(
    *,
    credential: ApiCredential,
    presented_key: str,
    now: datetime,
    required_scope: str | None = None,
) -> None:
    if now.tzinfo is None:
        raise ValueError("now must be timezone-aware")
    if credential.status is not CredentialStatus.ACTIVE:
        raise CredentialVerificationError("credential is not active")
    if credential.expires_at is not None and now >= credential.expires_at:
        raise CredentialVerificationError("credential is expired")

    prefix, separator, secret = presented_key.partition(".")
    if not separator or not prefix or not secret:
        raise CredentialVerificationError("malformed credential")
    if not compare_digest(prefix, credential.key_prefix):
        raise CredentialVerificationError("credential prefix mismatch")
    if not compare_digest(_hash_secret(secret), credential.secret_hash):
        raise CredentialVerificationError("credential secret mismatch")
    if required_scope is not None and required_scope not in credential.scopes:
        raise CredentialVerificationError("credential lacks required scope")


def revoke_credential(credential: ApiCredential) -> ApiCredential:
    if credential.status is CredentialStatus.REVOKED:
        return credential
    return replace(credential, status=CredentialStatus.REVOKED)
