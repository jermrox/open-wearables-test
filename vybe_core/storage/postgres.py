from __future__ import annotations

from datetime import datetime
from typing import Iterable
from uuid import UUID

from sqlalchemy import DateTime, Float, Index, MetaData, String, Table, Text, and_, delete, insert, select
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker
from sqlalchemy.schema import Column

from vybe_core.models.evidence import (
    Evidence,
    EvidenceKind,
    EvidenceProvenance,
    EvidenceQuality,
    EvidenceSource,
    SourceType,
)
from vybe_core.storage.contracts import EvidenceQuery, EvidenceStore


metadata = MetaData()


evidence_table = Table(
    "vybe_evidence",
    metadata,
    Column("evidence_id", PGUUID(as_uuid=True), primary_key=True),
    Column("person_id", PGUUID(as_uuid=True), nullable=False),
    Column("metric", String(128), nullable=False),
    Column("kind", String(32), nullable=False),
    Column("recorded_at", DateTime(timezone=True), nullable=False),
    Column("unit", String(64), nullable=True),
    Column("value", JSONB, nullable=True),
    Column("source_type", String(32), nullable=False),
    Column("provider", String(128), nullable=False),
    Column("device_id", String(255), nullable=True),
    Column("sensor", String(128), nullable=True),
    Column("source_record_id", String(255), nullable=True),
    Column("firmware_version", String(128), nullable=True),
    Column("signal_quality", Float, nullable=True),
    Column("confidence", Float, nullable=True),
    Column("completeness", Float, nullable=True),
    Column("quality_flags", JSONB, nullable=False),
    Column("ingested_at", DateTime(timezone=True), nullable=False),
    Column("processor", String(128), nullable=False),
    Column("processing_version", String(128), nullable=False),
    Column("raw_sha256", String(64), nullable=True),
    Column("parent_evidence_ids", JSONB, nullable=False),
    Column("metadata", JSONB, nullable=False),
)

Index("ix_vybe_evidence_person_recorded", evidence_table.c.person_id, evidence_table.c.recorded_at)
Index("ix_vybe_evidence_person_metric_recorded", evidence_table.c.person_id, evidence_table.c.metric, evidence_table.c.recorded_at)
Index("ix_vybe_evidence_source_record", evidence_table.c.provider, evidence_table.c.source_record_id)


def _row_for(person_id: UUID, item: Evidence) -> dict[str, object]:
    return {
        "evidence_id": item.id,
        "person_id": person_id,
        "metric": item.metric,
        "kind": item.kind.value,
        "recorded_at": item.recorded_at,
        "unit": item.unit,
        "value": item.value,
        "source_type": item.source.source_type.value,
        "provider": item.source.provider,
        "device_id": item.source.device_id,
        "sensor": item.source.sensor,
        "source_record_id": item.source.source_record_id,
        "firmware_version": item.source.firmware_version,
        "signal_quality": item.quality.signal_quality,
        "confidence": item.quality.confidence,
        "completeness": item.quality.completeness,
        "quality_flags": list(item.quality.flags),
        "ingested_at": item.provenance.ingested_at,
        "processor": item.provenance.processor,
        "processing_version": item.provenance.processing_version,
        "raw_sha256": item.provenance.raw_sha256,
        "parent_evidence_ids": [str(value) for value in item.provenance.parent_evidence_ids],
        "metadata": item.metadata,
    }


def _evidence_from_row(row) -> Evidence:
    return Evidence(
        id=row.evidence_id,
        metric=row.metric,
        kind=EvidenceKind(row.kind),
        recorded_at=row.recorded_at,
        unit=row.unit,
        value=row.value,
        source=EvidenceSource(
            source_type=SourceType(row.source_type),
            provider=row.provider,
            device_id=row.device_id,
            sensor=row.sensor,
            source_record_id=row.source_record_id,
            firmware_version=row.firmware_version,
        ),
        quality=EvidenceQuality(
            signal_quality=row.signal_quality,
            confidence=row.confidence,
            completeness=row.completeness,
            flags=tuple(row.quality_flags or ()),
        ),
        provenance=EvidenceProvenance(
            ingested_at=row.ingested_at,
            processor=row.processor,
            processing_version=row.processing_version,
            raw_sha256=row.raw_sha256,
            parent_evidence_ids=tuple(UUID(value) for value in (row.parent_evidence_ids or ())),
        ),
        metadata=dict(row.metadata or {}),
    )


class PostgresEvidenceStore(EvidenceStore):
    """Atomic append-only PostgreSQL implementation of EvidenceStore."""

    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine
        self._sessions = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async def create_schema(self) -> None:
        async with self._engine.begin() as connection:
            await connection.run_sync(metadata.create_all)

    async def append(self, person_id: UUID, evidence: Evidence) -> None:
        await self.append_many(person_id, (evidence,))

    async def append_many(self, person_id: UUID, evidence: Iterable[Evidence]) -> None:
        rows = [_row_for(person_id, item) for item in evidence]
        if not rows:
            return
        async with self._sessions() as session:
            async with session.begin():
                await session.execute(insert(evidence_table), rows)

    async def query(self, request: EvidenceQuery) -> tuple[Evidence, ...]:
        conditions = [evidence_table.c.person_id == request.person_id]
        if request.metrics:
            conditions.append(evidence_table.c.metric.in_(request.metrics))
        if request.start is not None:
            conditions.append(evidence_table.c.recorded_at >= request.start)
        if request.end is not None:
            conditions.append(evidence_table.c.recorded_at <= request.end)

        statement = select(evidence_table).where(and_(*conditions)).order_by(evidence_table.c.recorded_at.desc())
        if request.limit is not None:
            statement = statement.limit(request.limit)

        async with self._sessions() as session:
            result = await session.execute(statement)
            return tuple(_evidence_from_row(row) for row in result.fetchall())

    async def get(self, person_id: UUID, evidence_id: UUID) -> Evidence | None:
        statement = select(evidence_table).where(
            and_(
                evidence_table.c.person_id == person_id,
                evidence_table.c.evidence_id == evidence_id,
            )
        )
        async with self._sessions() as session:
            result = await session.execute(statement)
            row = result.first()
            return None if row is None else _evidence_from_row(row)
