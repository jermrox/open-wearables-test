from datetime import datetime, timedelta, timezone
from hashlib import sha256
from hmac import new as hmac_new
from uuid import uuid4

import pytest

from vybe_core.providers.oauth import create_authorization_request, validate_callback_state
from vybe_core.webhooks.verification import HMACWebhookVerifier, WebhookVerificationError


def test_oauth_state_and_expiry_validation():
    now = datetime.now(timezone.utc)
    request = create_authorization_request(
        application_id=uuid4(),
        person_id=uuid4(),
        provider="example",
        redirect_uri="https://example.test/callback",
        scopes=("read",),
        created_at=now,
        expires_at=now + timedelta(minutes=10),
    )
    validate_callback_state(request=request, returned_state=request.state, now=now + timedelta(minutes=1))

    with pytest.raises(ValueError):
        validate_callback_state(request=request, returned_state="wrong", now=now + timedelta(minutes=1))

    with pytest.raises(ValueError):
        validate_callback_state(request=request, returned_state=request.state, now=now + timedelta(minutes=10))


def test_hmac_webhook_verifier_rejects_replay_window_and_bad_signature():
    now = datetime.now(timezone.utc)
    secret = b"secret"
    body = b'{"event":"sample"}'
    ts = str(now.timestamp())
    expected = hmac_new(secret, ts.encode("utf-8") + b"." + body, sha256).hexdigest()
    verifier = HMACWebhookVerifier(
        secret=secret,
        signature_header="X-Signature",
        timestamp_header="X-Timestamp",
        tolerance=timedelta(minutes=5),
    )

    verifier.verify(
        body=body,
        headers={"X-Signature": f"sha256={expected}", "X-Timestamp": ts},
        received_at=now,
    )

    with pytest.raises(WebhookVerificationError):
        verifier.verify(
            body=body,
            headers={"X-Signature": "sha256=bad", "X-Timestamp": ts},
            received_at=now,
        )

    stale_ts = str((now - timedelta(minutes=6)).timestamp())
    stale_sig = hmac_new(secret, stale_ts.encode("utf-8") + b"." + body, sha256).hexdigest()
    with pytest.raises(WebhookVerificationError):
        verifier.verify(
            body=body,
            headers={"X-Signature": stale_sig, "X-Timestamp": stale_ts},
            received_at=now,
        )
