from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Annotated
from uuid import UUID

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request

from vybe_core.access.consent import ConsentStore
from vybe_core.access.policy import DataScope
from vybe_core.access.service import AccessContext, AuditedDeveloperHealthService
from vybe_core.audit.events import AuditStore
from vybe_core.auth.authenticate import AuthenticatedApplication, authenticate_api_key
from vybe_core.auth.contracts import AuthStore
from vybe_core.auth.credentials import CredentialVerificationError
from vybe_core.boundaries.public_api import MetricPoint, MetricQuery, PublicMetric
from vybe_core.storage.contracts import EvidenceStore


@dataclass(frozen=True, slots=True)
class ApiServices:
    auth_store: AuthStore
    evidence_store: EvidenceStore
    consent_store: ConsentStore
    audit_store: AuditStore


@dataclass(frozen=True, slots=True)
class RequestIdentity:
    authenticated: AuthenticatedApplication
    request_id: str | None
    ip_address: str | None


def create_app(services: ApiServices) -> FastAPI:
    app = FastAPI(
        title="Vybe Health API",
        version="0.1.0",
        description=(
            "Commercial API for normalized health capabilities. Raw device protocol, "
            "firmware, calibration, signal-processing, and proprietary model internals "
            "are intentionally not exposed."
        ),
    )
    health_service = AuditedDeveloperHealthService(
        evidence_store=services.evidence_store,
        consent_store=services.consent_store,
        audit_store=services.audit_store,
    )

    async def require_metrics_identity(
        request: Request,
        x_vybe_api_key: Annotated[str | None, Header(alias="X-Vybe-API-Key")] = None,
    ) -> RequestIdentity:
        if not x_vybe_api_key:
            raise HTTPException(status_code=401, detail="Missing API credential")
        try:
            authenticated = await authenticate_api_key(
                presented_key=x_vybe_api_key,
                now=datetime.now(timezone.utc),
                auth_store=services.auth_store,
                required_scope=DataScope.METRICS_READ,
            )
        except CredentialVerificationError as exc:
            raise HTTPException(status_code=401, detail="Invalid API credential") from exc

        forwarded_for = request.headers.get("x-forwarded-for")
        ip_address = forwarded_for.split(",", 1)[0].strip() if forwarded_for else (
            request.client.host if request.client else None
        )
        return RequestIdentity(
            authenticated=authenticated,
            request_id=request.headers.get("x-request-id"),
            ip_address=ip_address,
        )

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/v1/people/{person_id}/metrics/{metric}", response_model=list[MetricPoint])
    async def query_metric(
        person_id: UUID,
        metric: PublicMetric,
        start_at: Annotated[datetime, Query()],
        end_at: Annotated[datetime, Query()],
        identity: Annotated[RequestIdentity, Depends(require_metrics_identity)],
        limit: Annotated[int, Query(ge=1, le=1000)] = 1000,
    ) -> list[MetricPoint]:
        try:
            query = MetricQuery(
                person_id=person_id,
                metric=metric,
                start_at=start_at,
                end_at=end_at,
            )
            context = AccessContext(
                application_id=identity.authenticated.application_id,
                developer_grant=identity.authenticated.grant,
                actor_id=f"credential:{identity.authenticated.credential_id}",
                now=datetime.now(timezone.utc),
                request_id=identity.request_id,
                ip_address=identity.ip_address,
            )
            points = await health_service.query_metric(context=context, query=query, limit=limit)
        except PermissionError as exc:
            raise HTTPException(status_code=403, detail="Data access is not authorized") from exc
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return list(points)

    @app.get("/v1/people/{person_id}/metrics/{metric}/latest", response_model=MetricPoint | None)
    async def latest_metric(
        person_id: UUID,
        metric: PublicMetric,
        identity: Annotated[RequestIdentity, Depends(require_metrics_identity)],
    ) -> MetricPoint | None:
        context = AccessContext(
            application_id=identity.authenticated.application_id,
            developer_grant=identity.authenticated.grant,
            actor_id=f"credential:{identity.authenticated.credential_id}",
            now=datetime.now(timezone.utc),
            request_id=identity.request_id,
            ip_address=identity.ip_address,
        )
        try:
            return await health_service.latest_metric(
                context=context,
                person_id=person_id,
                metric=metric,
            )
        except PermissionError as exc:
            raise HTTPException(status_code=403, detail="Data access is not authorized") from exc
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    return app
