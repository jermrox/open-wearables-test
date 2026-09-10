from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from typing import Any, Protocol

from vybe_core.ingestion.envelope import IngestionEnvelope


class IdempotencyStore(Protocol):
    def seen(self, key: str) -> bool: ...

    def mark_seen(self, key: str) -> None: ...


def _canonical_payload_bytes(payload: bytes | str | dict[str, Any] | list[Any]) -> bytes:
    if isinstance(payload, bytes):
        return payload
    if isinstance(payload, str):
        return payload.encode("utf-8")
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def payload_sha256(envelope: IngestionEnvelope) -> str:
    return sha256(_canonical_payload_bytes(envelope.payload)).hexdigest()


@dataclass(frozen=True, slots=True)
class IdempotencyKeyBuilder:
    namespace: str = "vybe"

    def build(self, envelope: IngestionEnvelope) -> str:
        if envelope.external_event_id:
            material = f"{self.namespace}|{envelope.provider}|{envelope.external_event_id}"
        else:
            material = "|".join(
                [
                    self.namespace,
                    envelope.provider,
                    envelope.mode.value,
                    str(envelope.person_id),
                    payload_sha256(envelope),
                ]
            )
        return sha256(material.encode("utf-8")).hexdigest()
