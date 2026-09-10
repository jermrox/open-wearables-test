from __future__ import annotations

from datetime import datetime, timedelta, timezone
from hashlib import sha256
from hmac import new as hmac_new

import pytest

from vybe_core.providers.oura.webhook import (
    OuraWebhookVerifier,
    parse_oura_webhook_event,
    verify_oura_challenge,
)
from vybe_core.webhooks.verification import WebhookVerificationError


NOW = datetime(2026, 9, 10, 18, 0, tzinfo=timezone.utc)
SECRET = b"oura-client-secret"
BODY = b'{"event_type":"update","data_type":"sleep","object_id":"obj-1","event_time":"2026-09-10T17:59:30+00:00","user_id":"oura-user-1"}'


def signature(timestamp: str, body: bytes = BODY) -> str:
    return hmac_new(SECRET, timestamp.encode("utf-8") + body, sha256).hexdigest().upper()


def test_oura_signature_is_timestamp_plus_exact_raw_body_without_separator() -> None:
    timestamp = str(int(NOW.timestamp()))
    verifier = OuraWebhookVerifier(client_secret=SECRET)
    verifier.verify(
        body=BODY,
        headers={
            "X-Oura-Timestamp": timestamp,
            "X-Oura-Signature": signature(timestamp),
        },
        received_at=NOW,
    )


def test_oura_signature_verification_is_header_case_insensitive_and_hex_case_tolerant() -> None:
    timestamp = str(int(NOW.timestamp()))
    OuraWebhookVerifier(client_secret=SECRET).verify(
        body=BODY,
        headers={
            "x-oura-timestamp": timestamp,
            "x-oura-signature": signature(timestamp).lower(),
        },
        received_at=NOW,
    )


def test_oura_verifier_rejects_modified_body_and_stale_delivery() -> None:
    timestamp = str(int(NOW.timestamp()))
    verifier = OuraWebhookVerifier(client_secret=SECRET, tolerance=timedelta(minutes=5))

    with pytest.raises(WebhookVerificationError, match="invalid Oura webhook signature"):
        verifier.verify(
            body=BODY + b" ",
            headers={"x-oura-timestamp": timestamp, "x-oura-signature": signature(timestamp)},
            received_at=NOW,
        )

    stale_timestamp = str(int((NOW - timedelta(minutes=6)).timestamp()))
    with pytest.raises(WebhookVerificationError, match="outside allowed tolerance"):
        verifier.verify(
            body=BODY,
            headers={
                "x-oura-timestamp": stale_timestamp,
                "x-oura-signature": signature(stale_timestamp),
            },
            received_at=NOW,
        )


def test_oura_event_parser_preserves_object_fetch_identity() -> None:
    event = parse_oura_webhook_event(BODY)
    assert event.event_type == "update"
    assert event.data_type == "sleep"
    assert event.object_id == "obj-1"
    assert event.user_id == "oura-user-1"
    assert event.event_time == datetime(2026, 9, 10, 17, 59, 30, tzinfo=timezone.utc)


def test_oura_event_parser_fails_on_missing_required_field() -> None:
    with pytest.raises(ValueError, match="missing required fields"):
        parse_oura_webhook_event(b'{"event_type":"update"}')


def test_oura_challenge_uses_constant_time_token_check_and_echoes_challenge() -> None:
    assert verify_oura_challenge(
        expected_verification_token="secret-token",
        received_verification_token="secret-token",
        challenge="abc123",
    ) == {"challenge": "abc123"}

    with pytest.raises(WebhookVerificationError, match="verification token"):
        verify_oura_challenge(
            expected_verification_token="secret-token",
            received_verification_token="wrong",
            challenge="abc123",
        )
