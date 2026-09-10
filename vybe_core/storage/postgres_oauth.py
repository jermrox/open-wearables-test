from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, String, Table, and_, select, update
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker
from sqlalchemy.schema import Column

from vybe_core.providers.oauth_state import OAuthAuthorizationState, OAuthStateStore
from vybe_core.storage.postgres import metadata


oauth_state_table = Table(
    "vybe_oauth_authorization_states",
    metadata,
    Column("state_id", PGUUID(as_uuid=True), primary_key=True),
    Column("application_id", PGUUID(as_uuid=True), nullable=False),
    Column("person_id", PGUUID(as_uuid=True), nullable=False),
    Column("provider", String(128), nullable=False),
    Column("redirect_uri", String(2048), nullable=False),
    Column("scopes", JSONB, nullable=False),
    Column("state_digest", String(64), nullable=False),
    Column("verifier_reference", String(512), nullable=False),
    Column("code_challenge", String(128), nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("expires_at", DateTime(timezone=True), nullable=False),
    Column("consumed_at", DateTime(timezone=True), nullable=True),
)


def _from_row(row) -> OAuthAuthorizationState:
    return OAuthAuthorizationState(
        id=row.state_id,
        application_id=row.application_id,
        person_id=row.person_id,
        provider=row.provider,
        redirect_uri=row.redirect_uri,
        scopes=tuple(row.scopes or ()),
        state_digest=row.state_digest,
        verifier_reference=row.verifier_reference,
        code_challenge=row.code_challenge,
        created_at=row.created_at,
        expires_at=row.expires_at,
        consumed_at=row.consumed_at,
    )


class PostgresOAuthStateStore(OAuthStateStore):
    def __init__(self, engine: AsyncEngine) -> None:
        self._sessions = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async def put(self, state: OAuthAuthorizationState) -> None:
        async with self._sessions() as session:
            async with session.begin():
                await session.execute(
                    oauth_state_table.insert().values(
                        state_id=state.id,
                        application_id=state.application_id,
                        person_id=state.person_id,
                        provider=state.provider,
                        redirect_uri=state.redirect_uri,
                        scopes=list(state.scopes),
                        state_digest=state.state_digest,
                        verifier_reference=state.verifier_reference,
                        code_challenge=state.code_challenge,
                        created_at=state.created_at,
                        expires_at=state.expires_at,
                        consumed_at=state.consumed_at,
                    )
                )

    async def get(self, state_id: UUID) -> OAuthAuthorizationState | None:
        statement = select(oauth_state_table).where(oauth_state_table.c.state_id == state_id)
        async with self._sessions() as session:
            row = (await session.execute(statement)).first()
            return None if row is None else _from_row(row)

    async def consume(self, state_id: UUID, *, consumed_at: datetime) -> OAuthAuthorizationState:
        if consumed_at.tzinfo is None:
            raise ValueError("consumed_at must be timezone-aware")

        statement = (
            update(oauth_state_table)
            .where(
                and_(
                    oauth_state_table.c.state_id == state_id,
                    oauth_state_table.c.consumed_at.is_(None),
                    oauth_state_table.c.expires_at > consumed_at,
                )
            )
            .values(consumed_at=consumed_at)
            .returning(oauth_state_table)
        )
        async with self._sessions() as session:
            async with session.begin():
                row = (await session.execute(statement)).first()
                if row is None:
                    existing = await session.execute(
                        select(oauth_state_table.c.state_id).where(oauth_state_table.c.state_id == state_id)
                    )
                    if existing.first() is None:
                        raise KeyError(f"OAuth authorization state not found: {state_id}")
                    raise ValueError("OAuth authorization state expired or already consumed")
                return _from_row(row)
