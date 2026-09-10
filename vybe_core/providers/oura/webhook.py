from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from hmac import compare_digest, new as hmac_new
import json
from typing import Any

from vybe_core.webhooks.verification import WebhookVerificationError


@dataclass(frozen=True, slots=True)
class OuraWebhookEvent:
    event_type: str
    data_type: str
    object_id: str
    user_id: str
    event_time: datetime

    def __post_init__(self) -> None:
        if self.event_type not in {"create", "update", "delete"}:
            raise ValueError(f"unsupported Oura webhook event_type: {self.event_type}")
        for name, value in (
            ("data_type", self.data_type),
            ("object_id", self.object_id),
            ("user_id", self.user_id),
        ):
            if not value.strip():
                raise ValueError(f"Oura webhook {name} must not be empty")
        if self.event_time.tzinfo is None:
            raise ValueError("Oura webhook event_time must be timezone-aware")


@dataclass(frozen=True, slots=True)
class OuraWebhookVerifier:
    """Verifier matching Oura V2's documented signing algorithm exactly.

    Oura signs: HMAC-SHA256(client_secret, x-oura-timestamp + raw_json_body)
    and documents the digest as uppercase hexadecimal. Verification accepts hex
    case variations but never reserializes the body before signing.
    """

    client_secret: bytes
    tolerance: timedelta = timedelta(minutes=5)

    def verify(self, *, body: bytes, headers: dict[str, str], received_at: datetime) -> None:
        if received_at.tzinfo is None:
            raise ValueError("received_at must be timezone-aware")

        normalized_headers = {key.lower(): value for key, value in headers.items()}
        signature = normalized_headers.get("x-oura-signature")
        raw_timestamp = normalized_headers.get("x-oura-timestamp")
        if not signature:
            raise WebhookVerificationError("missing x-oura-signature")
        if not raw_timestamp:
            raise WebhookVerificationError("missing x-oura-timestamp")

        try:
            webhook_time = datetime.fromtimestamp(float(raw_timestamp), tz=timezone.utc)
        except (TypeError, ValueError, OverflowError) as exc:
            raise WebhookVerificationError("invalid x-oura-timestamp") from exc
        received_utc = received_at.astimezone(timezone.utc)
        if abs(received_utc - webhook_time) > self.tolerance:
            raise WebhookVerificationError("Oura webhook timestamp outside allowed tolerance")

        expected = hmac_new(
            self.client_secret,
            raw_timestamp.encode("utf-8") + body,
            sha256,
        ).hexdigest().upper()
        candidate = signature.removeprefix("sha256=").upper()
        if not compare_digest(expected, candidate):
            raise WebhookVerificationError("invalid Oura webhook signature")


def parse_oura_webhook_event(body: bytes) -> OuraWebhookEvent:
    try:
        payload: Any = json.loads(body)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("Oura webhook body must be valid JSON") from exc
    if not isinstance(payload, dict):
        raise ValueError("Oura webhook JSON root must be an object")

    required = ("event_type", "data_type", "object_id", "user_id", "event_time")
    missing = [field for field in required if field not in payload]
    if missing:
        raise ValueError(f"Oura webhook missing required fields: {', '.join(missing)}")

    event_time_raw = payload["event_time"]
    if not isinstance(event_time_raw, str):
        raise ValueError("Oura webhook event_time must be a string")
    normalized_time = event_time_raw[:-1] + "+00:00" if event_time_raw.endswith("Z") else event_time_raw
    try:
        event_time = datetime.fromisoformat(normalized_time)
    except ValueError as exc:
        raise ValueError("Oura webhook event_time must be valid ISO-8601") from exc

    values: dict[str, str] = {}
    for field in ("event_type", "data_type", "object_id", "user_id"):
        value = payload[field]
        if not isinstance(value, str):
            raise ValueError(f"Oura webhook {field} must be a string")
        values[field] = value

    return OuraWebhookEvent(event_time=event_time, **values)


def verify_oura_challenge(
    *,
    expected_verification_token: str,
    received_verification_token: str,
    challenge: str,
) -> dict[str, str]:
    if not expected_verification_token:
        raise ValueError("expected verification token must not be empty")
    if not challenge:
        raise ValueError("challenge must not be empty")
    if not compare_digest(expected_verification_token, received_verification_token):
        raise WebhookVerificationError("invalid Oura webhook verification token")
    return {"challenge": challenge}
