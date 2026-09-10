from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import DateTime, String, Table, and_, select
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker
from sqlalchemy.schema import Column

from vybe_core.ingestion.checkpoint import CheckpointStore, SyncCheckpoint
from vybe_core.storage.postgres import metadata


checkpoint_table = Table(
    "vybe_sync_checkpoints",
    metadata,
    Column("person_id", PGUUID(as_uuid=True), primary_key=True),
    Column("provider", String(128), primary_key=True),
    Column("stream", String(128), primary_key=True),
    Column("cursor", String, nullable=True),
    Column("updated_at", DateTime(timezone=True), nullable=False),
)

idempotency_table = Table(
    "vybe_idempotency_keys",
    metadata,
    Column("key", String(64), primary_key=True),
    Column("created_at", DateTime(timezone=True), nullable=False),
)


class PostgresCheckpointStore(CheckpointStore):
    def __init__(self, engine: AsyncEngine) -> None:
        self._sessions = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async def get(self, person_id: UUID, provider: str, stream: str) -> SyncCheckpoint | None:
        statement = select(checkpoint_table).where(
            and_(
                checkpoint_table.c.person_id == person_id,
                checkpoint_table.c.provider == provider,
                checkpoint_table.c.stream == stream,
            )
        )
        async with self._sessions() as session:
            row = (await session.execute(statement)).first()
            if row is None:
                return None
            return SyncCheckpoint(
                person_id=row.person_id,
                provider=row.provider,
                stream=row.stream,
                cursor=row.cursor,
                updated_at=row.updated_at,
            )

    async def put(self, checkpoint: SyncCheckpoint) -> None:
        statement = pg_insert(checkpoint_table).values(
            person_id=checkpoint.person_id,
            provider=checkpoint.provider,
            stream=checkpoint.stream,
            cursor=checkpoint.cursor,
            updated_at=checkpoint.updated_at,
        )
        statement = statement.on_conflict_do_update(
            index_elements=[
                checkpoint_table.c.person_id,
                checkpoint_table.c.provider,
                checkpoint_table.c.stream,
            ],
            set_={
                "cursor": statement.excluded.cursor,
                "updated_at": statement.excluded.updated_at,
            },
        )
        async with self._sessions() as session:
            async with session.begin():
                await session.execute(statement)


class PostgresIdempotencyStore:
    """Durable replay store used by ProviderIngestionExecutor."""

    def __init__(self, engine: AsyncEngine) -> None:
        self._sessions = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async def seen(self, key: str) -> bool:
        statement = select(idempotency_table.c.key).where(idempotency_table.c.key == key)
        async with self._sessions() as session:
            return (await session.execute(statement)).first() is not None

    async def mark_seen(self, key: str) -> None:
        if not key:
            raise ValueError("idempotency key must not be empty")
        statement = (
            pg_insert(idempotency_table)
            .values(key=key, created_at=datetime.now(timezone.utc))
            .on_conflict_do_nothing(index_elements=[idempotency_table.c.key])
        )
        async with self._sessions() as session:
            async with session.begin():
                await session.execute(statement)
