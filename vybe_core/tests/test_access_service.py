from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

import pytest

from vybe_core.access.consent import ConsentGrant
from vybe_core.access.policy import DataScope, DeveloperGrant
from vybe_core.access.service import AccessContext, AuditedDeveloperHealthService
from vybe_core.audit.events import AuditAction, AuditEvent
from vybe_core.boundaries.public_api import MetricQuery, PublicMetric
from vybe_core.models.evidence import Evidence, EvidenceProvenance, EvidenceQuality, EvidenceSource, SourceType
from vybe_core.storage.contracts import EvidenceQuery


NOW = datetime(2026, 9, 10, 18, 0, tzinfo=timezone.utc)


class EvidenceMemory:
    def __init__(self, items: tuple[Evidence, ...]) -> None:
        self.items = items

    async def append(self, person_id: UUID, evidence: Evidence) -> None:
        raise NotImplementedError

    async def append_many(self, person_id: UUID, evidence) -> None:
        raise NotImplementedError

    async def query(self, request: EvidenceQuery) -> tuple[Evidence, ...]:
        matches = [item for item in self.items if not request.metrics or item.metric in request.metrics]
        if request.start is not None:
            matches = [item for item in matches if item.recorded_at >= request.start]
        if request.end is not None:
            matches = [item for item in matches if item.recorded_at <= request.end]
        matches.sort(key=lambda item: item.recorded_at, reverse=True)
        if request.limit is not None:
            matches = matches[: request.limit]
        return tuple(matches)

    async def get(self, person_id: UUID, evidence_id: UUID):
        return None


class ConsentMemory:
    def __init__(self, grants: tuple[ConsentGrant, ...]) -> None:
        self.grants = grants

    async def put(self, grant: ConsentGrant) -> None:
        raise NotImplementedError

    async def get(self, consent_id: UUID):
        return next((grant for grant in self.grants if grant.id == consent_id), None)

    async def active_for(self, *, person_id: UUID, application_id: UUID, now: datetime):
        return tuple(
            grant
            for grant in self.grants
            if grant.person_id == person_id
            and grant.application_id == application_id
            and grant.active_at(now)
        )


class AuditMemory:
    def __init__(self) -> None:
        self.events: list[AuditEvent] = []

    async def append(self, event: AuditEvent) -> None:
        self.events.append(event)

    async def list_for_person(self, *, person_id: UUID, application_id: UUID | None = None, limit: int = 100):
        return tuple(self.events)


def metric(value: int, at: datetime) -> Evidence:
    return Evidence(
        metric="heart_rate",
        value=value,
        unit="bpm",
        recorded_at=at,
        source=EvidenceSource(source_type=SourceType.CLOUD_PROVIDER, provider="example"),
        quality=EvidenceQuality(confidence=0.9),
        provenance=EvidenceProvenance(
            ingested_at=NOW,
            processor="example",
            processing_version="1.0.0",
        ),
    )


def setup_service(*, with_consent: bool = True):
    application_id = uuid4()
    person_id = uuid4()
    grants = ()
    if with_consent:
        grants = (
            ConsentGrant(
                application_id=application_id,
                person_id=person_id,
                purpose="Show connected wearable metrics",
                scopes=frozenset({DataScope.METRICS_READ}),
                granted_at=NOW - timedelta(minutes=1),
            ),
        )
    audit = AuditMemory()
    service = AuditedDeveloperHealthService(
        evidence_store=EvidenceMemory((metric(70, NOW - timedelta(minutes=2)), metric(72, NOW - timedelta(minutes=1)))),
        consent_store=ConsentMemory(grants),
        audit_store=audit,
    )
    context = AccessContext(
        application_id=application_id,
        developer_grant=DeveloperGrant("developer-1", frozenset({DataScope.METRICS_READ})),
        actor_id="credential:test",
        now=NOW,
        request_id="req-1",
    )
    return service, context, audit, person_id


@pytest.mark.asyncio
async def test_authorized_metric_read_returns_public_points_and_audits() -> None:
    service, context, audit, person_id = setup_service()
    points = await service.query_metric(
        context=context,
        query=MetricQuery(
            person_id=person_id,
            metric=PublicMetric.HEART_RATE,
            start_at=NOW - timedelta(hours=1),
            end_at=NOW,
        ),
    )

    assert [point.value for point in points] == [72.0, 70.0]
    assert all(point.metric is PublicMetric.HEART_RATE for point in points)
    assert len(audit.events) == 1
    assert audit.events[0].action is AuditAction.DATA_READ
    assert audit.events[0].metadata["result_count"] == 2


@pytest.mark.asyncio
async def test_read_without_person_consent_fails_before_data_or_audit_success() -> None:
    service, context, audit, person_id = setup_service(with_consent=False)

    with pytest.raises(PermissionError, match="has not granted"):
        await service.latest_metric(
            context=context,
            person_id=person_id,
            metric=PublicMetric.HEART_RATE,
        )

    assert audit.events == []
