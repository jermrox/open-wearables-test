from datetime import datetime, timezone
from uuid import uuid4

import pytest

from vybe_core.models.evidence import (
    Evidence,
    EvidenceKind,
    EvidenceProvenance,
    EvidenceQuality,
    EvidenceSource,
    SourceType,
)


def base_source() -> EvidenceSource:
    return EvidenceSource(source_type=SourceType.DEVICE, provider="vybe_band")


def base_provenance(*, parents=()) -> EvidenceProvenance:
    return EvidenceProvenance(
        ingested_at=datetime.now(timezone.utc),
        processor="test",
        processing_version="1.0.0",
        parent_evidence_ids=parents,
    )


def test_quality_rejects_out_of_range_values() -> None:
    with pytest.raises(ValueError):
        EvidenceQuality(confidence=1.1)


def test_evidence_requires_timezone_aware_recorded_at() -> None:
    with pytest.raises(ValueError):
        Evidence(
            metric="heart_rate",
            value=72,
            unit="bpm",
            recorded_at=datetime.now(),
            source=base_source(),
            provenance=base_provenance(),
        )


def test_derivation_requires_parent_lineage() -> None:
    with pytest.raises(ValueError):
        Evidence(
            metric="hrv_baseline_delta",
            value=-0.12,
            recorded_at=datetime.now(timezone.utc),
            source=EvidenceSource(source_type=SourceType.DERIVED, provider="vybe_core"),
            provenance=base_provenance(),
            kind=EvidenceKind.DERIVATION,
        )


def test_derivation_accepts_parent_lineage() -> None:
    parent_id = uuid4()
    evidence = Evidence(
        metric="hrv_baseline_delta",
        value=-0.12,
        recorded_at=datetime.now(timezone.utc),
        source=EvidenceSource(source_type=SourceType.DERIVED, provider="vybe_core"),
        provenance=base_provenance(parents=(parent_id,)),
        kind=EvidenceKind.DERIVATION,
    )
    assert evidence.provenance.parent_evidence_ids == (parent_id,)
