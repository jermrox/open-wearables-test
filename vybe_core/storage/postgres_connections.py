from __future__ import annotations

from sqlalchemy import DateTime, String, Table, UniqueConstraint, and_, select
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker
from sqlalchemy.schema import Column

from vybe_core.providers.connections import ConnectionStatus, ProviderConnection, ProviderConnectionStore
from vybe_core.storage.postgres import metadata


provider_connection_table = Table(
    "vybe_provider_connections",
    metadata,
    Column("connection_id", PGUUID(as_uuid=True), primary_key=True),
    Column("application_id", PGUUID(as_uuid=True), nullable=False),
    Column("person_id", PGUUID(as_uuid=True), nullable=False),
    Column("provider", String(128), nullable=False),
    Column("status", String(32), nullable=False),
    Column("external_user_id", String(255), nullable=True),
    Column("token_reference", String(512), nullable=True),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("last_synced_at", DateTime(timezone=True), nullable=True),
    UniqueConstraint(
        "application_id",
        "person_id",
        "provider",
        name="uq_vybe_connection_application_person_provider",
    ),
)


def _from_row(row) -> ProviderConnection:
    return ProviderConnection(
        id=row.connection_id,
        application_id=row.application_id,
        person_id=row.person_id,
        provider=row.provider,
        status=ConnectionStatus(row.status),
        external_user_id=row.external_user_id,
        token_reference=row.token_reference,
        created_at=row.created_at,
        last_synced_at=row.last_synced_at,
    )


class PostgresProviderConnectionStore(ProviderConnectionStore):
    def __init__(self, engine: AsyncEngine) -> None:
        self._sessions = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async def put(self, connection: ProviderConnection) -> None:
        statement = pg_insert(provider_connection_table).values(
            connection_id=connection.id,
            application_id=connection.application_id,
            person_id=connection.person_id,
            provider=connection.provider,
            status=connection.status.value,
            external_user_id=connection.external_user_id,
            token_reference=connection.token_reference,
            created_at=connection.created_at,
            last_synced_at=connection.last_synced_at,
        )
        statement = statement.on_conflict_do_update(
            constraint="uq_vybe_connection_application_person_provider",
            set_={
                "connection_id": statement.excluded.connection_id,
                "status": statement.excluded.status,
                "external_user_id": statement.excluded.external_user_id,
                "token_reference": statement.excluded.token_reference,
                "last_synced_at": statement.excluded.last_synced_at,
            },
        )
        async with self._sessions() as session:
            async with session.begin():
                await session.execute(statement)

    async def get(self, connection_id):
        statement = select(provider_connection_table).where(provider_connection_table.c.connection_id == connection_id)
        async with self._sessions() as session:
            row = (await session.execute(statement)).first()
            return None if row is None else _from_row(row)

    async def get_for_person_provider(self, *, application_id, person_id, provider):
        statement = select(provider_connection_table).where(
            and_(
                provider_connection_table.c.application_id == application_id,
                provider_connection_table.c.person_id == person_id,
                provider_connection_table.c.provider == provider,
            )
        )
        async with self._sessions() as session:
            row = (await session.execute(statement)).first()
            return None if row is None else _from_row(row)

    async def list_for_person(self, *, application_id, person_id):
        statement = (
            select(provider_connection_table)
            .where(
                and_(
                    provider_connection_table.c.application_id == application_id,
                    provider_connection_table.c.person_id == person_id,
                )
            )
            .order_by(provider_connection_table.c.provider.asc())
        )
        async with self._sessions() as session:
            rows = (await session.execute(statement)).fetchall()
            return tuple(_from_row(row) for row in rows)
