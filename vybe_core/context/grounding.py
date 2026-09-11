from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable
from uuid import UUID

from vybe_core.context.compiler import CompiledContext, ContextReference


class GroundingError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class AnswerClaim:
    text: str
    evidence_ids: tuple[UUID, ...]

    def __post_init__(self) -> None:
        if not self.text.strip():
            raise ValueError("claim text must not be empty")
        if not self.evidence_ids:
            raise ValueError("source-backed claims must reference at least one evidence item")


@dataclass(frozen=True, slots=True)
class AnswerReference:
    evidence_id: UUID
    label: str
    provider: str
    source_record_id: str | None
    recorded_at: object
    confidence: float | None
    provenance: ContextReference


@dataclass(frozen=True, slots=True)
class GroundedAnswer:
    answer: str
    claims: tuple[AnswerClaim, ...]
    references: tuple[AnswerReference, ...]
    context_omitted_count: int


def ground_answer(
    *,
    answer: str,
    claims: Iterable[AnswerClaim],
    context: CompiledContext,
) -> GroundedAnswer:
    """Validate that every cited AI claim resolves to supplied evidence.

    This function does not judge medical correctness. It enforces a more basic
    invariant: the model may only cite evidence that was actually supplied in its
    bounded context packet. Unknown or hallucinated evidence IDs fail closed.
    """

    if not answer.strip():
        raise GroundingError("answer must not be empty")

    claims_tuple = tuple(claims)
    context_items = {item.evidence_id: item for item in context.items}
    referenced_ids: list[UUID] = []

    for claim in claims_tuple:
        for evidence_id in claim.evidence_ids:
            if evidence_id not in context_items:
                raise GroundingError(f"claim references evidence outside compiled context: {evidence_id}")
            if evidence_id not in referenced_ids:
                referenced_ids.append(evidence_id)

    references = tuple(
        AnswerReference(
            evidence_id=evidence_id,
            label=context_items[evidence_id].reference.source_label,
            provider=context_items[evidence_id].provider,
            source_record_id=context_items[evidence_id].reference.source_record_id,
            recorded_at=context_items[evidence_id].recorded_at,
            confidence=context_items[evidence_id].confidence,
            provenance=context_items[evidence_id].reference,
        )
        for evidence_id in referenced_ids
    )

    return GroundedAnswer(
        answer=answer.strip(),
        claims=claims_tuple,
        references=references,
        context_omitted_count=context.omitted_count,
    )
