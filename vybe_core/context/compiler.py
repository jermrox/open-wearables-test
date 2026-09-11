from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Iterable
from uuid import UUID

from vybe_core.models.evidence import Evidence, SourceType


@dataclass(frozen=True, slots=True)
class ContextReference:
    """Inspectable source reference that can be surfaced with an AI answer."""

    evidence_id: UUID
    source_type: SourceType
    provider: str
    source_record_id: str | None
    device_id: str | None
    sensor: str | None
    firmware_version: str | None
    processor: str
    processing_version: str
    ingested_at: datetime
    raw_sha256: str | None
    parent_evidence_ids: tuple[UUID, ...]
    source_label: str


@dataclass(frozen=True, slots=True)
class ContextItem:
    evidence_id: UUID
    metric: str
    recorded_at: datetime
    value: object
    unit: str | None
    provider: str
    confidence: float | None
    reference: ContextReference


@dataclass(frozen=True, slots=True)
class CompiledContext:
    question: str
    items: tuple[ContextItem, ...]
    references: tuple[ContextReference, ...]
    omitted_count: int

    def reference_for(self, evidence_id: UUID) -> ContextReference | None:
        return next((reference for reference in self.references if reference.evidence_id == evidence_id), None)


class ContextCompiler:
    """Build a bounded, source-backed evidence packet for downstream AI reasoning.

    The compiler never invents measurements, source identifiers, confidence, or
    citations. Every reference is derived from canonical Evidence provenance so
    downstream answers can explain exactly which source records support a claim.
    """

    def __init__(self, max_items: int = 200) -> None:
        if max_items < 1:
            raise ValueError("max_items must be positive")
        self.max_items = max_items

    def compile(self, question: str, evidence: Iterable[Evidence]) -> CompiledContext:
        if not question.strip():
            raise ValueError("question must not be empty")

        ranked = sorted(
            evidence,
            key=lambda item: (
                item.quality.confidence if item.quality.confidence is not None else -1.0,
                item.recorded_at,
            ),
            reverse=True,
        )
        selected = ranked[: self.max_items]

        references = tuple(self._reference(item) for item in selected)
        items = tuple(
            ContextItem(
                evidence_id=item.id,
                metric=item.metric,
                recorded_at=item.recorded_at,
                value=item.value,
                unit=item.unit,
                provider=item.source.provider,
                confidence=item.quality.confidence,
                reference=reference,
            )
            for item, reference in zip(selected, references, strict=True)
        )

        return CompiledContext(
            question=question.strip(),
            items=items,
            references=references,
            omitted_count=max(0, len(ranked) - len(selected)),
        )

    @staticmethod
    def _reference(item: Evidence) -> ContextReference:
        record = item.source.source_record_id
        source_label = item.source.provider
        if record:
            source_label = f"{source_label}:{record}"

        return ContextReference(
            evidence_id=item.id,
            source_type=item.source.source_type,
            provider=item.source.provider,
            source_record_id=record,
            device_id=item.source.device_id,
            sensor=item.source.sensor,
            firmware_version=item.source.firmware_version,
            processor=item.provenance.processor,
            processing_version=item.provenance.processing_version,
            ingested_at=item.provenance.ingested_at,
            raw_sha256=item.provenance.raw_sha256,
            parent_evidence_ids=item.provenance.parent_evidence_ids,
            source_label=source_label,
        )
