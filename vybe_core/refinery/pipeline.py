from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from vybe_core.models.evidence import Evidence
from vybe_core.refinery.deduplication import DuplicateGroup, group_duplicates
from vybe_core.refinery.normalization import UnsupportedUnitError, normalize_evidence
from vybe_core.refinery.plausibility import check_plausibility


@dataclass(frozen=True, slots=True)
class RejectedEvidence:
    evidence: Evidence
    stage: str
    reasons: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class RefineryResult:
    accepted: tuple[Evidence, ...]
    rejected: tuple[RejectedEvidence, ...]
    duplicate_groups: tuple[DuplicateGroup, ...]


class EvidenceRefinery:
    """Deterministic preprocessing boundary before persistence or AI use.

    The refinery never mutates input evidence and never silently drops records.
    Rejected and duplicate records remain inspectable in the result.
    """

    def process(self, evidence: Iterable[Evidence]) -> RefineryResult:
        normalized: list[Evidence] = []
        rejected: list[RejectedEvidence] = []

        for item in evidence:
            try:
                candidate = normalize_evidence(item)
            except (UnsupportedUnitError, TypeError, ValueError) as exc:
                rejected.append(RejectedEvidence(item, "normalization", (str(exc),)))
                continue

            plausibility = check_plausibility(candidate)
            if not plausibility.accepted:
                rejected.append(RejectedEvidence(candidate, "plausibility", plausibility.reasons))
                continue

            normalized.append(candidate)

        duplicate_groups = group_duplicates(normalized)
        accepted = tuple(group.primary for group in duplicate_groups)

        return RefineryResult(
            accepted=accepted,
            rejected=tuple(rejected),
            duplicate_groups=duplicate_groups,
        )
