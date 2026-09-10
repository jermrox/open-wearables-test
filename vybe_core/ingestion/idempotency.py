from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from typing import Protocol

from vybe_core.ingestion.envelope import IngestionEnvelope


class IdempotencyStore(Protocol):
    def seen(self, key: str) -> bool: ...

    def mark_seen(self, key: str) -> None: ...


@dataclass(frozen=True, slots=True)
class IdempotencyKeyBuilder:
    namespace: str = "vybe"

    def build(self, envelope: IngestionEnvelope) -> str:
        if envelope.source_event_id:
            material = f"{self.namespace}|{envelope.provider}|{envelope.source_event_id}"
        else:
            material = "|".join(
                [
                    self.namespace,
                    envelope.provider,
                    envelope.mode.value,
                    envelope.subject_id,
                    envelope.received_at.isoformat(),
                    envelope.payload_sha256,
                ]
            )
        return sha256(material.encode("utf-8")).hexdigest()
