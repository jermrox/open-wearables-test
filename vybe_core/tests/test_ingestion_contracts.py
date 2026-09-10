from datetime import datetime, timezone
from uuid import uuid4

import pytest

from vybe_core.ingestion.checkpoint import SyncCheckpoint
from vybe_core.ingestion.envelope import IngestionEnvelope, IngestionMode
from vybe_core.storage.contracts import EvidenceQuery


def test_ingestion_envelope_requires_aware_time() -> None:
    with pytest.raises(ValueError):
        IngestionEnvelope(
            person_id=uuid4(),
            provider="apple_health",
            mode=IngestionMode.SDK_PUSH,
            received_at=datetime.now(),
            payload={},
        )


def test_checkpoint_treats_cursor_as_opaque() -> None:
    checkpoint = SyncCheckpoint(
        person_id=uuid4(),
        provider="garmin",
        stream="activities",
        cursor="opaque-provider-token:abc123",
        updated_at=datetime.now(timezone.utc),
    )
    assert checkpoint.cursor == "opaque-provider-token:abc123"


def test_evidence_query_rejects_inverted_range() -> None:
    now = datetime.now(timezone.utc)
    with pytest.raises(ValueError):
        EvidenceQuery(person_id=uuid4(), start=now, end=now.replace(year=now.year - 1))
