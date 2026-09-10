from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from vybe_core.access.consent import ConsentGrant, revoke_consent, require_data_access
from vybe_core.access.policy import DataScope, DeveloperGrant


NOW = datetime(2026, 9, 10, 18, 0, tzinfo=timezone.utc)


def grant(*, application_id, person_id, scopes=frozenset({DataScope.METRICS_READ})) -> ConsentGrant:
    return ConsentGrant(
        person_id=person_id,
        application_id=application_id,
        purpose="Provide wearable health metrics in the connected application",
        scopes=scopes,
        granted_at=NOW,
        expires_at=NOW + timedelta(days=30),
    )


def test_data_access_requires_platform_scope_and_person_consent() -> None:
    application_id = uuid4()
    person_id = uuid4()
    developer = DeveloperGrant("developer-1", frozenset({DataScope.METRICS_READ}))
    consent = grant(application_id=application_id, person_id=person_id)

    require_data_access(
        developer_grant=developer,
        consent_grants=(consent,),
        application_id=application_id,
        person_id=person_id,
        scope=DataScope.METRICS_READ,
        now=NOW + timedelta(minutes=1),
    )


def test_consent_does_not_override_missing_developer_scope() -> None:
    application_id = uuid4()
    person_id = uuid4()
    developer = DeveloperGrant("developer-1", frozenset({DataScope.EVENTS_READ}))

    with pytest.raises(PermissionError, match="developer grant lacks"):
        require_data_access(
            developer_grant=developer,
            consent_grants=(grant(application_id=application_id, person_id=person_id),),
            application_id=application_id,
            person_id=person_id,
            scope=DataScope.METRICS_READ,
            now=NOW,
        )


def test_developer_scope_does_not_override_missing_or_wrong_consent() -> None:
    application_id = uuid4()
    person_id = uuid4()
    developer = DeveloperGrant("developer-1", frozenset({DataScope.METRICS_READ}))
    wrong_app = grant(application_id=uuid4(), person_id=person_id)

    with pytest.raises(PermissionError, match="has not granted"):
        require_data_access(
            developer_grant=developer,
            consent_grants=(wrong_app,),
            application_id=application_id,
            person_id=person_id,
            scope=DataScope.METRICS_READ,
            now=NOW,
        )


def test_revoked_and_expired_consent_fail_closed() -> None:
    application_id = uuid4()
    person_id = uuid4()
    developer = DeveloperGrant("developer-1", frozenset({DataScope.METRICS_READ}))
    active = grant(application_id=application_id, person_id=person_id)
    revoked = revoke_consent(active, revoked_at=NOW + timedelta(minutes=1))

    with pytest.raises(PermissionError):
        require_data_access(
            developer_grant=developer,
            consent_grants=(revoked,),
            application_id=application_id,
            person_id=person_id,
            scope=DataScope.METRICS_READ,
            now=NOW + timedelta(minutes=2),
        )

    with pytest.raises(PermissionError):
        require_data_access(
            developer_grant=developer,
            consent_grants=(active,),
            application_id=application_id,
            person_id=person_id,
            scope=DataScope.METRICS_READ,
            now=NOW + timedelta(days=30),
        )
