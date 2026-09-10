from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import datetime
from enum import Enum
from typing import Protocol
from uuid import UUID, uuid4

from vybe_core.access.policy import DataScope, DeveloperGrant, require_scope


class ConsentStatus(str, Enum):
    ACTIVE = "active"
    REVOKED = "revoked"


@dataclass(frozen=True, slots=True)
class ConsentGrant:
    """A person's explicit authorization for one application and purpose."""

    person_id: UUID
    application_id: UUID
    purpose: str
    scopes: frozenset[DataScope]
    granted_at: datetime
    expires_at: datetime | None = None
    status: ConsentStatus = ConsentStatus.ACTIVE
    revoked_at: datetime | None = None
    id: UUID = field(default_factory=uuid4)

    def __post_init__(self) -> None:
        if not self.purpose.strip():
            raise ValueError("consent purpose must not be empty")
        if not self.scopes:
            raise ValueError("consent must grant at least one data scope")
        if self.granted_at.tzinfo is None:
            raise ValueError("granted_at must be timezone-aware")
        if self.expires_at is not None:
            if self.expires_at.tzinfo is None:
                raise ValueError("expires_at must be timezone-aware")
            if self.expires_at <= self.granted_at:
                raise ValueError("expires_at must be after granted_at")
        if self.revoked_at is not None:
            if self.revoked_at.tzinfo is None:
                raise ValueError("revoked_at must be timezone-aware")
            if self.revoked_at < self.granted_at:
                raise ValueError("revoked_at cannot predate granted_at")
        if self.status is ConsentStatus.REVOKED and self.revoked_at is None:
            raise ValueError("revoked consent requires revoked_at")
        if self.status is ConsentStatus.ACTIVE and self.revoked_at is not None:
            raise ValueError("active consent cannot have revoked_at")

    def active_at(self, now: datetime) -> bool:
        if now.tzinfo is None:
            raise ValueError("now must be timezone-aware")
        if self.status is not ConsentStatus.ACTIVE:
            return False
        return self.expires_at is None or now < self.expires_at


class ConsentStore(Protocol):
    async def put(self, grant: ConsentGrant) -> None: ...

    async def get(self, consent_id: UUID) -> ConsentGrant | None: ...

    async def active_for(
        self,
        *,
        person_id: UUID,
        application_id: UUID,
        now: datetime,
    ) -> tuple[ConsentGrant, ...]: ...


def revoke_consent(grant: ConsentGrant, *, revoked_at: datetime) -> ConsentGrant:
    if revoked_at.tzinfo is None:
        raise ValueError("revoked_at must be timezone-aware")
    if grant.status is ConsentStatus.REVOKED:
        return grant
    return replace(grant, status=ConsentStatus.REVOKED, revoked_at=revoked_at)


def require_data_access(
    *,
    developer_grant: DeveloperGrant,
    consent_grants: tuple[ConsentGrant, ...],
    application_id: UUID,
    person_id: UUID,
    scope: DataScope,
    now: datetime,
) -> None:
    """Require both platform authorization and an active person consent grant."""

    require_scope(developer_grant, scope)
    allowed = any(
        grant.application_id == application_id
        and grant.person_id == person_id
        and grant.active_at(now)
        and scope in grant.scopes
        for grant in consent_grants
    )
    if not allowed:
        raise PermissionError(
            f"person has not granted application access for scope: {scope.value}"
        )
