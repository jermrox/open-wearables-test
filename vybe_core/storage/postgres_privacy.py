from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, Index, String, Table, and_, select
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker
from sqlalchemy.schema import Column

from vybe_core.access.consent import ConsentGrant, ConsentStatus, ConsentStore
from vybe_core.access.policy import DataScope
from vybe_core.audit.events import AuditAction, AuditEvent, AuditStore
from vybe_core.storage.postgres import metadata


consent_table = Table(
    "vybe_consent_grants",
    metadata,
    Column("consent_id", PGUUID(as_uuid=True), primary_key=True),
    Column("person_id", PGUUID(as_uuid=True), nullable=False),
    Column("application_id", PGUUID(as_uuid=True), nullable=False),
    Column("purpose", String(512), nullable=False),
    Column("scopes", JSONB, nullable=False),
    Column("status", String(32), nullable=False),
    Column("granted_at", DateTime(timezone=True), nullable=False),
    Column("expires_at", DateTime(timezone=True), nullable=True),
    Column("revoked_at", DateTime(timezone=True), nullable=True),
)
Index(
    "ix_vybe_consent_person_application",
    consent_table.c.person_id,
    consent_table.c.application_id,
)


audit_table = Table(
    "vybe_audit_events",
    metadata,
    Column("audit_id", PGUUID(as_uuid=True), primary_key=True),
    Column("action", String(64), nullable=False),
    Column("occurred_at", DateTime(timezone=True), nullable=False),
    Column("application_id", PGUUID(as_uuid=True), nullable=True),
    Column("person_id", PGUUID(as_uuid=True), nullable=True),
    Column("actor_id", String(255), nullable=True),
    Column("resource_type", String(128), nullable=True),
    Column("resource_id", String(255), nullable=True),
    Column("request_id", String(255), nullable=True),
    Column("ip_address", String(128), nullable=True),
    Column("metadata", JSONB, nullable=False),
)
Index("ix_vybe_audit_person_occurred", audit_table.c.person_id, audit_table.c.occurred_at)
Index("ix_vybe_audit_application_occurred", audit_table.c.application_id, audit_table.c.occurred_at)


def _consent_from_row(row) -> ConsentGrant:
    return ConsentGrant(
        id=row.consent_id,
        person_id=row.person_id,
        application_id=row.application_id,
        purpose=row.purpose,
        scopes=frozenset(DataScope(value) for value in (row.scopes or ())),
        status=ConsentStatus(row.status),
        granted_at=row.granted_at,
        expires_at=row.expires_at,
        revoked_at=row.revoked_at,
    )


def _audit_from_row(row) -> AuditEvent:
    return AuditEvent(
        id=row.audit_id,
        action=AuditAction(row.action),
        occurred_at=row.occurred_at,
        application_id=row.application_id,
        person_id=row.person_id,
        actor_id=row.actor_id,
        resource_type=row.resource_type,
        resource_id=row.resource_id,
        request_id=row.request_id,
        ip_address=row.ip_address,
        metadata=dict(row.metadata or {}),
    )


class PostgresConsentStore(ConsentStore):
    def __init__(self, engine: AsyncEngine) -> None:
        self._sessions = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async def put(self, grant: ConsentGrant) -> None:
        statement = pg_insert(consent_table).values(
            consent_id=grant.id,
            person_id=grant.person_id,
            application_id=grant.application_id,
            purpose=grant.purpose,
            scopes=[scope.value for scope in sorted(grant.scopes, key=lambda item: item.value)],
            status=grant.status.value,
            granted_at=grant.granted_at,
            expires_at=grant.expires_at,
            revoked_at=grant.revoked_at,
        )
        statement = statement.on_conflict_do_update(
            index_elements=[consent_table.c.consent_id],
            set_={
                "status": statement.excluded.status,
                "expires_at": statement.excluded.expires_at,
                "revoked_at": statement.excluded.revoked_at,
            },
        )
        async with self._sessions() as session:
            async with session.begin():
                await session.execute(statement)

    async def get(self, consent_id: UUID) -> ConsentGrant | None:
        async with self._sessions() as session:
            row = (
                await session.execute(select(consent_table).where(consent_table.c.consent_id == consent_id))
            ).first()
            return None if row is None else _consent_from_row(row)

    async def active_for(
        self,
        *,
        person_id: UUID,
        application_id: UUID,
        now: datetime,
    ) -> tuple[ConsentGrant, ...]:
        if now.tzinfo is None:
            raise ValueError("now must be timezone-aware")
        statement = (
            select(consent_table)
            .where(
                and_(
                    consent_table.c.person_id == person_id,
                    consent_table.c.application_id == application_id,
                    consent_table.c.status == ConsentStatus.ACTIVE.value,
                    (consent_table.c.expires_at.is_(None) | (consent_table.c.expires_at > now)),
                )
            )
            .order_by(consent_table.c.granted_at.desc())
        )
        async with self._sessions() as session:
            rows = (await session.execute(statement)).fetchall()
            return tuple(_consent_from_row(row) for row in rows)


class PostgresAuditStore(AuditStore):
    def __init__(self, engine: AsyncEngine) -> None:
        self._sessions = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async def append(self, event: AuditEvent) -> None:
        async with self._sessions() as session:
            async with session.begin():
                await session.execute(
                    audit_table.insert().values(
                        audit_id=event.id,
                        action=event.action.value,
                        occurred_at=event.occurred_at,
                        application_id=event.application_id,
                        person_id=event.person_id,
                        actor_id=event.actor_id,
                        resource_type=event.resource_type,
                        resource_id=event.resource_id,
                        request_id=event.request_id,
                        ip_address=event.ip_address,
                        metadata=event.metadata,
                    )
                )

    async def list_for_person(
        self,
        *,
        person_id: UUID,
        application_id: UUID | None = None,
        limit: int = 100,
    ) -> tuple[AuditEvent, ...]:
        if limit <= 0:
            raise ValueError("limit must be positive")
        conditions = [audit_table.c.person_id == person_id]
        if application_id is not None:
            conditions.append(audit_table.c.application_id == application_id)
        statement = (
            select(audit_table)
            .where(and_(*conditions))
            .order_by(audit_table.c.occurred_at.desc())
            .limit(limit)
        )
        async with self._sessions() as session:
            rows = (await session.execute(statement)).fetchall()
            return tuple(_audit_from_row(row) for row in rows)
