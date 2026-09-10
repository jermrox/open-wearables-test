from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Protocol
from uuid import UUID, uuid4


class ConnectionStatus(str, Enum):
    PENDING = "pending"
    ACTIVE = "active"
    REAUTH_REQUIRED = "reauth_required"
    REVOKED = "revoked"
    ERROR = "error"


@dataclass(frozen=True, slots=True)
class ProviderConnection:
    application_id: UUID
    person_id: UUID
    provider: str
    created_at: datetime
    status: ConnectionStatus = ConnectionStatus.PENDING
    external_user_id: str | None = None
    token_reference: str | None = None
    last_synced_at: datetime | None = None
    id: UUID = field(default_factory=uuid4)

    def __post_init__(self) -> None:
        if not self.provider.strip():
            raise ValueError("provider must not be empty")
        if self.created_at.tzinfo is None:
            raise ValueError("created_at must be timezone-aware")
        if self.last_synced_at is not None and self.last_synced_at.tzinfo is None:
            raise ValueError("last_synced_at must be timezone-aware")
        if self.last_synced_at is not None and self.last_synced_at < self.created_at:
            raise ValueError("last_synced_at cannot predate connection creation")


class TokenVault(Protocol):
    """Secret-storage boundary for OAuth/provider credentials.

    Core application records store only opaque references. Implementations may
    use a cloud secret manager, encrypted database column, HSM/KMS-backed store,
    or another audited secret store.
    """

    def put(self, *, namespace: str, secret: str) -> str: ...

    def get(self, reference: str) -> str: ...

    def delete(self, reference: str) -> None: ...
