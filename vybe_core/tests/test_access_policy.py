from __future__ import annotations

import pytest

from vybe_core.access.policy import (
    DataScope,
    DeveloperGrant,
    EngineCapability,
    require_scope,
)


def test_grant_allows_only_explicit_data_scopes() -> None:
    grant = DeveloperGrant(developer_id="dev_1", scopes=frozenset({DataScope.METRICS_READ}))

    assert grant.allows(DataScope.METRICS_READ)
    assert not grant.allows(DataScope.EVENTS_READ)


def test_commercial_grant_never_exposes_private_engine() -> None:
    grant = DeveloperGrant(developer_id="dev_1", scopes=frozenset(DataScope))

    for capability in EngineCapability:
        assert not grant.allows_engine_capability(capability)


def test_require_scope_fails_closed() -> None:
    grant = DeveloperGrant(developer_id="dev_1", scopes=frozenset())

    with pytest.raises(PermissionError):
        require_scope(grant, DataScope.METRICS_READ)
