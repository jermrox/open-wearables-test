from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from vybe_core.providers.oauth_state import (
    consume_state,
    create_oauth_launch,
    retrieve_pkce_verifier,
    validate_returned_state,
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


def test_oauth_launch_persists_digest_and_vault_reference_not_raw_secrets() -> None:
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

    assert launch.returned_state_token not in launch.state.state_digest
    verifier = retrieve_pkce_verifier(launch.state, token_vault=vault)
    assert verifier not in launch.state.verifier_reference
    assert launch.state.code_challenge


def test_returned_state_is_expiring_and_single_use() -> None:
    vault = MemoryVault()
    launch = create_oauth_launch(
        application_id=uuid4(),
        person_id=uuid4(),
        provider="garmin",
        redirect_uri="https://example.com/oauth/callback",
        scopes=("activity",),
        created_at=NOW,
        expires_at=NOW + timedelta(minutes=5),
        token_vault=vault,
    )

    validate_returned_state(
        state=launch.state,
        returned_state_token=launch.returned_state_token,
        now=NOW + timedelta(minutes=1),
    )
    consumed = consume_state(launch.state, consumed_at=NOW + timedelta(minutes=1))

    with pytest.raises(ValueError, match="already consumed"):
        validate_returned_state(
            state=consumed,
            returned_state_token=launch.returned_state_token,
            now=NOW + timedelta(minutes=2),
        )


def test_wrong_or_expired_state_fails_closed() -> None:
    vault = MemoryVault()
    launch = create_oauth_launch(
        application_id=uuid4(),
        person_id=uuid4(),
        provider="polar",
        redirect_uri="https://example.com/oauth/callback",
        scopes=("accesslink.read_all",),
        created_at=NOW,
        expires_at=NOW + timedelta(minutes=5),
        token_vault=vault,
    )

    with pytest.raises(ValueError, match="mismatch"):
        validate_returned_state(state=launch.state, returned_state_token="wrong", now=NOW)

    with pytest.raises(ValueError, match="expired"):
        validate_returned_state(
            state=launch.state,
            returned_state_token=launch.returned_state_token,
            now=NOW + timedelta(minutes=5),
        )
