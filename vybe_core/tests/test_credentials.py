from datetime import datetime, timedelta, timezone

import pytest

from vybe_core.auth.credentials import (
    CredentialVerificationError,
    issue_credential,
    revoke_credential,
    verify_credential,
)
from vybe_core.auth.models import Application


def make_app(now: datetime) -> Application:
    from uuid import uuid4

    return Application(organization_id=uuid4(), name="Test App", created_at=now)


def test_issue_returns_plaintext_once_and_stores_hash_only():
    now = datetime.now(timezone.utc)
    credential, plaintext = issue_credential(
        application=make_app(now),
        created_at=now,
        scopes=frozenset({"metrics:read"}),
    )
    assert plaintext.startswith(credential.key_prefix + ".")
    assert plaintext not in credential.secret_hash
    assert credential.secret_hash not in plaintext


def test_verify_accepts_valid_key_and_scope():
    now = datetime.now(timezone.utc)
    credential, plaintext = issue_credential(
        application=make_app(now),
        created_at=now,
        scopes=frozenset({"metrics:read"}),
    )
    verify_credential(
        credential=credential,
        presented_key=plaintext,
        now=now,
        required_scope="metrics:read",
    )


def test_verify_rejects_wrong_secret():
    now = datetime.now(timezone.utc)
    credential, plaintext = issue_credential(
        application=make_app(now),
        created_at=now,
        scopes=frozenset({"metrics:read"}),
    )
    prefix = plaintext.split(".", 1)[0]
    with pytest.raises(CredentialVerificationError):
        verify_credential(
            credential=credential,
            presented_key=f"{prefix}.wrong",
            now=now,
        )


def test_verify_rejects_missing_scope():
    now = datetime.now(timezone.utc)
    credential, plaintext = issue_credential(
        application=make_app(now),
        created_at=now,
        scopes=frozenset({"metrics:read"}),
    )
    with pytest.raises(CredentialVerificationError):
        verify_credential(
            credential=credential,
            presented_key=plaintext,
            now=now,
            required_scope="events:read",
        )


def test_expired_and_revoked_keys_fail_closed():
    now = datetime.now(timezone.utc)
    credential, plaintext = issue_credential(
        application=make_app(now),
        created_at=now,
        expires_at=now + timedelta(hours=1),
        scopes=frozenset({"metrics:read"}),
    )
    with pytest.raises(CredentialVerificationError):
        verify_credential(
            credential=credential,
            presented_key=plaintext,
            now=now + timedelta(hours=1),
        )

    revoked = revoke_credential(credential)
    with pytest.raises(CredentialVerificationError):
        verify_credential(
            credential=revoked,
            presented_key=plaintext,
            now=now,
        )
