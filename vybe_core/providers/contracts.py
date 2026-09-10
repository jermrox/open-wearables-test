from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import AsyncIterator

from vybe_core.models.evidence import Evidence


class DeliveryMode(str, Enum):
    DIRECT_DEVICE = "direct_device"
    CLIENT_PUSH = "client_push"
    REST_PULL = "rest_pull"
    WEBHOOK = "webhook"
    FILE_IMPORT = "file_import"


@dataclass(frozen=True, slots=True)
class ProviderCapabilities:
    delivery_modes: frozenset[DeliveryMode] = field(default_factory=frozenset)
    supports_historical_sync: bool = False
    supports_live_sync: bool = False
    max_historical_days: int | None = None


@dataclass(frozen=True, slots=True)
class SyncWindow:
    start: datetime
    end: datetime

    def __post_init__(self) -> None:
        if self.start.tzinfo is None or self.end.tzinfo is None:
            raise ValueError("sync window timestamps must be timezone-aware")
        if self.end < self.start:
            raise ValueError("sync window end must be >= start")


class EvidenceProvider(ABC):
    """Infrastructure-independent boundary for every Vybe data source.

    Implementations retrieve or receive source-native data, validate it, and emit
    canonical Evidence. Persistence, job dispatch, and AI reasoning do not belong
    in provider implementations. The requested stream is explicit so a single
    provider adapter can safely expose multiple vendor data collections.
    """

    @property
    @abstractmethod
    def provider_id(self) -> str:
        raise NotImplementedError

    @property
    @abstractmethod
    def capabilities(self) -> ProviderCapabilities:
        raise NotImplementedError

    @abstractmethod
    async def collect(
        self,
        subject_id: str,
        stream: str,
        window: SyncWindow,
    ) -> AsyncIterator[Evidence]:
        """Emit normalized evidence for one named stream and bounded time window."""
        if False:
            yield  # pragma: no cover
