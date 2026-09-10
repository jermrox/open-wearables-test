from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Iterable
from uuid import UUID

from vybe_core.models.evidence import Evidence


@dataclass(frozen=True, slots=True)
class ContextItem:
    evidence_id: UUID
    metric: str
    recorded_at: datetime
    value: object
    unit: str | None
    provider: str
    confidence: float | None


@dataclass(frozen=True, slots=True)
class CompiledContext:
    question: str
    items: tuple[ContextItem, ...]
    omitted_count: int


class ContextCompiler:
    """Builds a bounded, inspectable evidence packet for an AI model.

    This layer never invents measurements and never performs clinical reasoning.
    It selects already-validated evidence for downstream reasoning.
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

        items = tuple(
            ContextItem(
                evidence_id=item.id,
                metric=item.metric,
                recorded_at=item.recorded_at,
                value=item.value,
                unit=item.unit,
                provider=item.source.provider,
                confidence=item.quality.confidence,
            )
            for item in selected
        )

        return CompiledContext(
            question=question.strip(),
            items=items,
            omitted_count=max(0, len(ranked) - len(selected)),
        )
