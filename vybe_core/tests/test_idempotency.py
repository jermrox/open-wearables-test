from datetime import datetime, timezone
from uuid import uuid4

from vybe_core.ingestion.envelope import IngestionEnvelope, IngestionMode
from vybe_core.ingestion.idempotency import IdempotencyKeyBuilder, payload_sha256


def _envelope(payload, *, external_event_id=None):
    return IngestionEnvelope(
        person_id=uuid4(),
        provider="test",
        mode=IngestionMode.WEBHOOK,
        received_at=datetime.now(timezone.utc),
        payload=payload,
        external_event_id=external_event_id,
    )


def test_dict_payload_hash_is_order_independent():
    a = _envelope({"b": 2, "a": 1})
    b = IngestionEnvelope(
        person_id=a.person_id,
        provider=a.provider,
        mode=a.mode,
        received_at=a.received_at,
        payload={"a": 1, "b": 2},
    )
    assert payload_sha256(a) == payload_sha256(b)
    assert IdempotencyKeyBuilder().build(a) == IdempotencyKeyBuilder().build(b)


def test_received_at_does_not_change_payload_fallback_key():
    person = uuid4()
    a = IngestionEnvelope(person_id=person, provider="test", mode=IngestionMode.PULL, received_at=datetime(2026, 1, 1, tzinfo=timezone.utc), payload={"x": 1})
    b = IngestionEnvelope(person_id=person, provider="test", mode=IngestionMode.PULL, received_at=datetime(2026, 1, 2, tzinfo=timezone.utc), payload={"x": 1})
    assert IdempotencyKeyBuilder().build(a) == IdempotencyKeyBuilder().build(b)


def test_external_event_id_is_stable_across_payload_retries():
    person = uuid4()
    a = IngestionEnvelope(person_id=person, provider="test", mode=IngestionMode.WEBHOOK, received_at=datetime.now(timezone.utc), payload={"attempt": 1}, external_event_id="evt-1")
    b = IngestionEnvelope(person_id=person, provider="test", mode=IngestionMode.WEBHOOK, received_at=datetime.now(timezone.utc), payload={"attempt": 2}, external_event_id="evt-1")
    assert IdempotencyKeyBuilder().build(a) == IdempotencyKeyBuilder().build(b)
