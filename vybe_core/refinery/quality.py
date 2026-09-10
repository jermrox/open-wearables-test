from __future__ import annotations

from dataclasses import dataclass, replace

from vybe_core.models.evidence import Evidence, EvidenceQuality


@dataclass(frozen=True, slots=True)
class QualityAssessment:
    evidence: Evidence
    verified_completeness: float
    flags: tuple[str, ...]


def assess_quality(evidence: Evidence) -> QualityAssessment:
    """Assess only metadata completeness that Vybe can verify deterministically.

    This deliberately does not invent signal quality or physiological confidence.
    Existing provider/device-supplied values are preserved unchanged.
    """

    checks = {
        "provider_present": bool(evidence.source.provider.strip()),
        "processor_present": bool(evidence.provenance.processor.strip()),
        "processing_version_present": bool(evidence.provenance.processing_version.strip()),
        "recorded_at_present": evidence.recorded_at is not None,
        "ingested_at_present": evidence.provenance.ingested_at is not None,
        "unit_present_when_numeric": not (
            isinstance(evidence.value, (int, float))
            and not isinstance(evidence.value, bool)
            and evidence.unit is None
        ),
    }

    passed = sum(1 for value in checks.values() if value)
    completeness = passed / len(checks)
    flags = tuple(name for name, value in checks.items() if not value)

    existing = evidence.quality
    quality = EvidenceQuality(
        signal_quality=existing.signal_quality,
        confidence=existing.confidence,
        completeness=completeness,
        flags=tuple(dict.fromkeys((*existing.flags, *flags))),
    )
    updated = replace(evidence, quality=quality)
    return QualityAssessment(updated, completeness, flags)
