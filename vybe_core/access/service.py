from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from vybe_core.access.consent import ConsentStore, require_data_access
from vybe_core.access.policy import DataScope, DeveloperGrant
from vybe_core.audit.events import AuditAction, AuditEvent, AuditStore
from vybe_core.boundaries.public_api import MetricPoint, MetricQuery, PublicMetric
from vybe_core.models.evidence import Evidence
from vybe_core.storage.contracts import EvidenceQuery, EvidenceStore


@dataclass(frozen=True, slots=True)
class AccessContext:
    application_id: UUID
    developer_grant: DeveloperGrant
    actor_id: str
    now: datetime
    request_id: str | None = None
    ip_address: str | None = None

    def __post_init__(self) -> None:
        if self.now.tzinfo is None:
            raise ValueError("now must be timezone-aware")
        if not self.actor_id.strip():
            raise ValueError("actor_id must not be empty")


def _metric_point(item: Evidence, expected_metric: PublicMetric) -> MetricPoint:
    if item.metric != expected_metric.value:
        raise ValueError("evidence metric does not match requested public metric")
    if not isinstance(item.value, (int, float)) or isinstance(item.value, bool):
        raise ValueError("public metric evidence must contain a numeric value")
    if not item.unit:
        raise ValueError("public metric evidence must contain a unit")
    return MetricPoint(
        metric=expected_metric,
        value=float(item.value),
        unit=item.unit,
        recorded_at=item.recorded_at,
        confidence=item.quality.confidence,
    )


class AuditedDeveloperHealthService:
    """Commercial data-read surface with mandatory authorization and audit.

    A successful read requires BOTH a platform developer grant and an active
    person-to-application consent grant. Only normalized public metric objects
    leave this service; raw signals and proprietary engine internals are absent
    by construction.
    """

    def __init__(
        self,
        *,
        evidence_store: EvidenceStore,
        consent_store: ConsentStore,
        audit_store: AuditStore,
    ) -> None:
        self._evidence_store = evidence_store
        self._consent_store = consent_store
        self._audit_store = audit_store

    async def query_metric(
        self,
        *,
        context: AccessContext,
        query: MetricQuery,
        limit: int = 1000,
    ) -> tuple[MetricPoint, ...]:
        if limit <= 0:
            raise ValueError("limit must be positive")

        consent = await self._consent_store.active_for(
            person_id=query.person_id,
            application_id=context.application_id,
            now=context.now,
        )
        require_data_access(
            developer_grant=context.developer_grant,
            consent_grants=consent,
            application_id=context.application_id,
            person_id=query.person_id,
            scope=DataScope.METRICS_READ,
            now=context.now,
        )

        evidence = await self._evidence_store.query(
            EvidenceQuery(
                person_id=query.person_id,
                metrics=(query.metric.value,),
                start=query.start_at,
                end=query.end_at,
                limit=limit,
            )
        )
        points = tuple(_metric_point(item, query.metric) for item in evidence)

        await self._audit_store.append(
            AuditEvent(
                action=AuditAction.DATA_READ,
                occurred_at=context.now,
                application_id=context.application_id,
                person_id=query.person_id,
                actor_id=context.actor_id,
                resource_type="metric",
                resource_id=query.metric.value,
                request_id=context.request_id,
                ip_address=context.ip_address,
                metadata={
                    "scope": DataScope.METRICS_READ.value,
                    "result_count": len(points),
                    "start_at": query.start_at.isoformat(),
                    "end_at": query.end_at.isoformat(),
                },
            )
        )
        return points

    async def latest_metric(
        self,
        *,
        context: AccessContext,
        person_id: UUID,
        metric: PublicMetric,
    ) -> MetricPoint | None:
        consent = await self._consent_store.active_for(
            person_id=person_id,
            application_id=context.application_id,
            now=context.now,
        )
        require_data_access(
            developer_grant=context.developer_grant,
            consent_grants=consent,
            application_id=context.application_id,
            person_id=person_id,
            scope=DataScope.METRICS_READ,
            now=context.now,
        )

        evidence = await self._evidence_store.query(
            EvidenceQuery(person_id=person_id, metrics=(metric.value,), end=context.now, limit=1)
        )
        point = None if not evidence else _metric_point(evidence[0], metric)

        await self._audit_store.append(
            AuditEvent(
                action=AuditAction.DATA_READ,
                occurred_at=context.now,
                application_id=context.application_id,
                person_id=person_id,
                actor_id=context.actor_id,
                resource_type="metric.latest",
                resource_id=metric.value,
                request_id=context.request_id,
                ip_address=context.ip_address,
                metadata={
                    "scope": DataScope.METRICS_READ.value,
                    "result_count": 0 if point is None else 1,
                },
            )
        )
        return point
