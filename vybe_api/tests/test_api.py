from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

import httpx
import pytest

from vybe_api.app import ApiServices, create_app
from vybe_core.access.consent import ConsentGrant
from vybe_core.access.policy import DataScope
from vybe_core.audit.events import AuditEvent
from vybe_core.auth.credentials import issue_credential
from vybe_core.auth.models import ApiCredential, Application, Organization
from vybe_core.models.evidence import Evidence, EvidenceProvenance, EvidenceQuality, EvidenceSource, SourceType
from vybe_core.storage.contracts import EvidenceQuery


NOW = datetime.now(timezone.utc)


class MemoryAuthStore:
    def __init__(self) -> None:
        self.organizations: dict[UUID, Organization] = {}
        self.applications: dict[UUID, Application] = {}
        self.credentials: dict[str, ApiCredential] = {}

    async def put_organization(self, organization: Organization) -> None:
        self.organizations[organization.id] = organization

    async def put_application(self, application: Application) -> None:
        self.applications[application.id] = application

    async def put_credential(self, credential: ApiCredential) -> None:
        self.credentials[credential.key_prefix] = credential

    async def get_application(self, application_id: UUID) -> Application | None:
        return self.applications.get(application_id)

    async def get_credential_by_prefix(self, key_prefix: str) -> ApiCredential | None:
        return self.credentials.get(key_prefix)


class MemoryEvidenceStore:
    def __init__(self) -> None:
        self.items: list[tuple[UUID, Evidence]] = []

    async def append(self, person_id: UUID, evidence: Evidence) -> None:
        self.items.append((person_id, evidence))

    async def append_many(self, person_id: UUID, evidence) -> None:
        self.items.extend((person_id, item) for item in evidence)

    async def query(self, request: EvidenceQuery) -> tuple[Evidence, ...]:
        matches = [
            item
            for owner, item in self.items
            if owner == request.person_id and (not request.metrics or item.metric in request.metrics)
        ]
        if request.start is not None:
            matches = [item for item in matches if item.recorded_at >= request.start]
        if request.end is not None:
            matches = [item for item in matches if item.recorded_at <= request.end]
        matches.sort(key=lambda item: item.recorded_at, reverse=True)
        if request.limit is not None:
            matches = matches[: request.limit]
        return tuple(matches)

    async def get(self, person_id: UUID, evidence_id: UUID) -> Evidence | None:
        return next((item for owner, item in self.items if owner == person_id and item.id == evidence_id), None)


class MemoryConsentStore:
    def __init__(self) -> None:
        self.grants: dict[UUID, ConsentGrant] = {}

    async def put(self, grant: ConsentGrant) -> None:
        self.grants[grant.id] = grant

    async def get(self, consent_id: UUID) -> ConsentGrant | None:
        return self.grants.get(consent_id)

    async def active_for(self, *, person_id: UUID, application_id: UUID, now: datetime):
        return tuple(
            grant
            for grant in self.grants.values()
            if grant.person_id == person_id and grant.application_id == application_id and grant.active_at(now)
        )


class MemoryAuditStore:
    def __init__(self) -> None:
        self.events: list[AuditEvent] = []

    async def append(self, event: AuditEvent) -> None:
        self.events.append(event)

    async def list_for_person(self, *, person_id: UUID, application_id: UUID | None = None, limit: int = 100):
        events = [event for event in self.events if event.person_id == person_id]
        if application_id is not None:
            events = [event for event in events if event.application_id == application_id]
        return tuple(events[:limit])


async def configured_app(*, grant_consent: bool):
    auth = MemoryAuthStore()
    evidence = MemoryEvidenceStore()
    consent = MemoryConsentStore()
    audit = MemoryAuditStore()

    organization = Organization(name="SDK Customer", created_at=NOW)
    application = Application(organization_id=organization.id, name="Consumer App", created_at=NOW)
    credential, plaintext = issue_credential(
        application=application,
        created_at=NOW,
        scopes=frozenset({DataScope.METRICS_READ.value}),
    )
    await auth.put_organization(organization)
    await auth.put_application(application)
    await auth.put_credential(credential)

    person_id = uuid4()
    await evidence.append(
        person_id,
        Evidence(
            metric="heart_rate",
            value=71,
            unit="bpm",
            recorded_at=NOW - timedelta(minutes=1),
            source=EvidenceSource(source_type=SourceType.CLOUD_PROVIDER, provider="example"),
            quality=EvidenceQuality(confidence=0.9),
            provenance=EvidenceProvenance(
                ingested_at=NOW,
                processor="example",
                processing_version="1.0.0",
            ),
        ),
    )
    if grant_consent:
        await consent.put(
            ConsentGrant(
                person_id=person_id,
                application_id=application.id,
                purpose="Display connected health metrics",
                scopes=frozenset({DataScope.METRICS_READ}),
                granted_at=NOW - timedelta(minutes=5),
            )
        )

    app = create_app(
        ApiServices(
            auth_store=auth,
            evidence_store=evidence,
            consent_store=consent,
            audit_store=audit,
        )
    )
    return app, plaintext, person_id, audit


@pytest.mark.asyncio
async def test_health_is_public_but_metric_data_requires_key() -> None:
    app, _, person_id, _ = await configured_app(grant_consent=True)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        assert (await client.get("/health")).status_code == 200
        response = await client.get(f"/v1/people/{person_id}/metrics/heart_rate/latest")
        assert response.status_code == 401


@pytest.mark.asyncio
async def test_valid_key_without_person_consent_is_forbidden() -> None:
    app, key, person_id, audit = await configured_app(grant_consent=False)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(
            f"/v1/people/{person_id}/metrics/heart_rate/latest",
            headers={"X-Vybe-API-Key": key},
        )
    assert response.status_code == 403
    assert audit.events == []


@pytest.mark.asyncio
async def test_authorized_latest_metric_returns_normalized_output_and_audits() -> None:
    app, key, person_id, audit = await configured_app(grant_consent=True)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(
            f"/v1/people/{person_id}/metrics/heart_rate/latest",
            headers={"X-Vybe-API-Key": key, "X-Request-ID": "request-123"},
        )
    assert response.status_code == 200
    body = response.json()
    assert body["metric"] == "heart_rate"
    assert body["value"] == 71.0
    assert body["unit"] == "bpm"
    assert body["confidence"] == 0.9
    assert len(audit.events) == 1
    assert audit.events[0].request_id == "request-123"


@pytest.mark.asyncio
async def test_commercial_api_has_no_raw_signal_route() -> None:
    app, key, person_id, _ = await configured_app(grant_consent=True)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(
            f"/v1/people/{person_id}/raw-signals",
            headers={"X-Vybe-API-Key": key},
        )
    assert response.status_code == 404
