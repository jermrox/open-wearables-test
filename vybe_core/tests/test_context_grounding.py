from datetime import datetime, timezone
from uuid import uuid4

import pytest

from vybe_core.context.compiler import ContextCompiler
from vybe_core.context.grounding import AnswerClaim, GroundingError, ground_answer
from vybe_core.models.evidence import Evidence, EvidenceProvenance, EvidenceQuality, EvidenceSource, SourceType


NOW = datetime(2026, 9, 10, 20, 0, tzinfo=timezone.utc)


def evidence() -> Evidence:
    return Evidence(
        metric="ldl_cholesterol",
        value=118,
        unit="mg/dL",
        recorded_at=NOW,
        source=EvidenceSource(
            source_type=SourceType.CLINICAL,
            provider="lab_partner",
            source_record_id="result-123",
        ),
        provenance=EvidenceProvenance(
            ingested_at=NOW,
            processor="lab_result_adapter",
            processing_version="1.0.0",
            raw_sha256="a" * 64,
        ),
        quality=EvidenceQuality(confidence=1.0),
    )


def test_context_preserves_source_and_provenance_for_answer_references() -> None:
    item = evidence()
    context = ContextCompiler().compile("What changed?", [item])

    reference = context.references[0]
    assert reference.evidence_id == item.id
    assert reference.source_type is SourceType.CLINICAL
    assert reference.provider == "lab_partner"
    assert reference.source_record_id == "result-123"
    assert reference.processor == "lab_result_adapter"
    assert reference.raw_sha256 == "a" * 64
    assert reference.source_label == "lab_partner:result-123"


def test_grounded_answer_builds_reference_from_supplied_context_only() -> None:
    item = evidence()
    context = ContextCompiler().compile("What changed?", [item])

    answer = ground_answer(
        answer="Your latest LDL result is 118 mg/dL.",
        claims=[AnswerClaim("Latest LDL is 118 mg/dL", (item.id,))],
        context=context,
    )

    assert len(answer.references) == 1
    assert answer.references[0].evidence_id == item.id
    assert answer.references[0].label == "lab_partner:result-123"


def test_grounding_rejects_hallucinated_evidence_reference() -> None:
    context = ContextCompiler().compile("What changed?", [evidence()])

    with pytest.raises(GroundingError, match="outside compiled context"):
        ground_answer(
            answer="Unsupported claim",
            claims=[AnswerClaim("Unsupported", (uuid4(),))],
            context=context,
        )
