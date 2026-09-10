from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from typing import Iterable

from vybe_core.models.evidence import Evidence


@dataclass(frozen=True, slots=True)
class DuplicateGroup:
    primary: Evidence
    duplicates: tuple[Evidence, ...]


def _same_value(a: Evidence, b: Evidence) -> bool:
    if isinstance(a.value, (int, float)) and isinstance(b.value, (int, float)):
        return abs(float(a.value) - float(b.value)) <= 1e-9
    return a.value == b.value


def group_duplicates(
    evidence: Iterable[Evidence],
    *,
    time_tolerance: timedelta = timedelta(seconds=1),
) -> tuple[DuplicateGroup, ...]:
    """Group only high-confidence duplicates.

    Evidence is considered duplicate when metric, canonical unit, provider,
    source record identity (when present), value, and timestamp are effectively
    the same. Similar measurements from different sources are intentionally not
    deduplicated; those belong to conflict resolution.
    """

    pending = sorted(tuple(evidence), key=lambda item: item.recorded_at)
    consumed: set[int] = set()
    groups: list[DuplicateGroup] = []

    for index, item in enumerate(pending):
        if index in consumed:
            continue

        matches: list[Evidence] = []
        for other_index in range(index + 1, len(pending)):
            if other_index in consumed:
                continue
            other = pending[other_index]
            if other.recorded_at - item.recorded_at > time_tolerance:
                break
            if item.metric != other.metric or item.unit != other.unit:
                continue
            if item.source.provider != other.source.provider:
                continue
            if item.source.source_record_id and other.source.source_record_id:
                if item.source.source_record_id != other.source.source_record_id:
                    continue
            if not _same_value(item, other):
                continue
            matches.append(other)
            consumed.add(other_index)

        groups.append(DuplicateGroup(primary=item, duplicates=tuple(matches)))

    return tuple(groups)
