from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Protocol
from uuid import UUID, uuid4


class AuditAction(str, Enum):
    DATA_READ = "data.read"
    DATA_EXPORT = "data.export"
    CONNECTION_CREATED = "connection.created"
    CONNECTION_REVOKED = "connection.revoked"
    CONSENT_GRANTED = "consent.granted"
    CONSENT_REVOKED = "consent.revoked"
    CREDENTIAL_CREATED = "credential.created"
    CREDENTIAL_REVOKED = "credential.revoked"
    OAUTH_COMPLETED = "oauth.completed"
    TOKEN_REFRESHED = "token.refreshed"
    WEBHOOK_ACCEPTED = "webhook.accepted"
    WEBHOOK_REJECTED = "webhook.rejected"


@dataclass(frozen=True, slots=True)
class AuditEvent:
    action: AuditAction
    occurred_at: datetime
    application_id: UUID | None = None
    person_id: UUID | None = None
    actor_id: str | None = None
    resource_type: str | None = None
    resource_id: str | None = None
    request_id: str | None = None
    ip_address: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    id: UUID = field(default_factory=uuid4)

    def __post_init__(self) -> None:
        if self.occurred_at.tzinfo is None:
            raise ValueError("occurred_at must be timezone-aware")
        if self.resource_id is not None and not self.resource_type:
            raise ValueError("resource_id requires resource_type")


class AuditStore(Protocol):
    async def append(self, event: AuditEvent) -> None: ...

    async def list_for_person(
        self,
        *,
        person_id: UUID,
        application_id: UUID | None = None,
        limit: int = 100,
    ) -> tuple[AuditEvent, ...]: ...
