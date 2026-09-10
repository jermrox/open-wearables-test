from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from hashlib import sha256
from hmac import compare_digest, new as hmac_new
from typing import Protocol


class WebhookVerificationError(ValueError):
    pass


class WebhookVerifier(Protocol):
    def verify(self, *, body: bytes, headers: dict[str, str], received_at: datetime) -> None: ...


@dataclass(frozen=True, slots=True)
class HMACWebhookVerifier:
    """Reusable HMAC-SHA256 verifier for providers with this signature model.

    Provider adapters remain responsible for extracting the provider-specific
    timestamp/signature headers and canonical message format when they differ.
    """

    secret: bytes
    signature_header: str
    timestamp_header: str | None = None
    tolerance: timedelta = timedelta(minutes=5)

    def verify(self, *, body: bytes, headers: dict[str, str], received_at: datetime) -> None:
        if received_at.tzinfo is None:
            raise ValueError("received_at must be timezone-aware")
        signature = headers.get(self.signature_header)
        if not signature:
            raise WebhookVerificationError("missing webhook signature")

        signed_payload = body
        if self.timestamp_header is not None:
            raw_timestamp = headers.get(self.timestamp_header)
            if not raw_timestamp:
                raise WebhookVerificationError("missing webhook timestamp")
            try:
                timestamp = datetime.fromtimestamp(float(raw_timestamp), tz=received_at.tzinfo)
            except (TypeError, ValueError, OverflowError) as exc:
                raise WebhookVerificationError("invalid webhook timestamp") from exc
            if abs(received_at - timestamp) > self.tolerance:
                raise WebhookVerificationError("webhook timestamp outside allowed tolerance")
            signed_payload = raw_timestamp.encode("utf-8") + b"." + body

        expected = hmac_new(self.secret, signed_payload, sha256).hexdigest()
        candidate = signature.removeprefix("sha256=")
        if not compare_digest(expected, candidate):
            raise WebhookVerificationError("invalid webhook signature")
