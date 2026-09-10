from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import FrozenSet


class DataScope(str, Enum):
    METRICS_READ = "metrics:read"
    EVENTS_READ = "events:read"
    INSIGHTS_READ = "insights:read"
    WEBHOOKS_RECEIVE = "webhooks:receive"
    EXPORT_READ = "export:read"


class EngineCapability(str, Enum):
    RAW_SIGNAL_ACCESS = "raw_signal_access"
    CALIBRATION_ACCESS = "calibration_access"
    FIRMWARE_ACCESS = "firmware_access"
    ALGORITHM_IMPLEMENTATION = "algorithm_implementation"


@dataclass(frozen=True, slots=True)
class DeveloperGrant:
    developer_id: str
    scopes: FrozenSet[DataScope]

    def allows(self, scope: DataScope) -> bool:
        return scope in self.scopes

    def allows_engine_capability(self, capability: EngineCapability) -> bool:
        """Commercial developer grants never expose proprietary engine internals."""
        return False


def require_scope(grant: DeveloperGrant, scope: DataScope) -> None:
    if not grant.allows(scope):
        raise PermissionError(f"developer grant lacks required scope: {scope.value}")
