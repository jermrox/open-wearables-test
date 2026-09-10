from __future__ import annotations

from typing import Protocol
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, String, Table, UniqueConstraint, and_, select
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker
from sqlalchemy.schema import Column

from vybe_core.auth.models import ApiCredential, Application, CredentialStatus, Organization
from vybe_core.storage.postgres import metadata


organization_table = Table(
    "vybe_organizations",
    metadata,
    Column("organization_id", PGUUID(as_uuid=True), primary_key=True),
    Column("name", String(255), nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
)

application_table = Table(
    "vybe_applications",
    metadata,
    Column("application_id", PGUUID(as_uuid=True), primary_key=True),
    Column("organization_id", PGUUID(as_uuid=True), ForeignKey("vybe_organizations.organization_id", ondelete="CASCADE"), nullable=False),
    Column("name", String(255), nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    UniqueConstraint("organization_id", "name", name="uq_vybe_application_organization_name"),
)

credential_table = Table(
    "vybe_api_credentials",
    metadata,
    Column("credential_id", PGUUID(as_uuid=True), primary_key=True),
    Column("application_id", PGUUID(as_uuid=True), ForeignKey("vybe_applications.application_id", ondelete="CASCADE"), nullable=False),
    Column("key_prefix", String(128), nullable=False, unique=True),
    Column("secret_hash", String(64), nullable=False),
    Column("scopes", JSONB, nullable=False),
    Column("status", String(32), nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("expires_at", DateTime(timezone=True), nullable=True),
)


class AuthStore(Protocol):
    async def put_organization(self, organization: Organization) -> None: ...
    async def put_application(self, application: Application) -> None: ...
    async def put_credential(self, credential: ApiCredential) -> None: ...
    async def get_application(self, application_id: UUID) -> Application | None: ...
    async def get_credential_by_prefix(self, key_prefix: str) -> ApiCredential | None: ...


def _application_from_row(row) -> Application:
    return Application(
        id=row.application_id,
        organization_id=row.organization_id,
        name=row.name,
        created_at=row.created_at,
    )


def _credential_from_row(row) -> ApiCredential:
    return ApiCredential(
        id=row.credential_id,
        application_id=row.application_id,
        key_prefix=row.key_prefix,
        secret_hash=row.secret_hash,
        scopes=frozenset(row.scopes or ()),
        status=CredentialStatus(row.status),
        created_at=row.created_at,
        expires_at=row.expires_at,
    )


class PostgresAuthStore(AuthStore):
    def __init__(self, engine: AsyncEngine) -> None:
        self._sessions = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async def put_organization(self, organization: Organization) -> None:
        async with self._sessions() as session:
            async with session.begin():
                await session.execute(
                    pg_insert(organization_table)
                    .values(
                        organization_id=organization.id,
                        name=organization.name,
                        created_at=organization.created_at,
                    )
                    .on_conflict_do_nothing(index_elements=[organization_table.c.organization_id])
                )

    async def put_application(self, application: Application) -> None:
        async with self._sessions() as session:
            async with session.begin():
                await session.execute(
                    pg_insert(application_table)
                    .values(
                        application_id=application.id,
                        organization_id=application.organization_id,
                        name=application.name,
                        created_at=application.created_at,
                    )
                    .on_conflict_do_nothing(index_elements=[application_table.c.application_id])
                )

    async def put_credential(self, credential: ApiCredential) -> None:
        statement = pg_insert(credential_table).values(
            credential_id=credential.id,
            application_id=credential.application_id,
            key_prefix=credential.key_prefix,
            secret_hash=credential.secret_hash,
            scopes=sorted(credential.scopes),
            status=credential.status.value,
            created_at=credential.created_at,
            expires_at=credential.expires_at,
        )
        statement = statement.on_conflict_do_update(
            index_elements=[credential_table.c.credential_id],
            set_={
                "secret_hash": statement.excluded.secret_hash,
                "scopes": statement.excluded.scopes,
                "status": statement.excluded.status,
                "expires_at": statement.excluded.expires_at,
            },
        )
        async with self._sessions() as session:
            async with session.begin():
                await session.execute(statement)

    async def get_application(self, application_id: UUID) -> Application | None:
        async with self._sessions() as session:
            row = (
                await session.execute(
                    select(application_table).where(application_table.c.application_id == application_id)
                )
            ).first()
            return None if row is None else _application_from_row(row)

    async def get_credential_by_prefix(self, key_prefix: str) -> ApiCredential | None:
        async with self._sessions() as session:
            row = (
                await session.execute(
                    select(credential_table).where(credential_table.c.key_prefix == key_prefix)
                )
            ).first()
            return None if row is None else _credential_from_row(row)
