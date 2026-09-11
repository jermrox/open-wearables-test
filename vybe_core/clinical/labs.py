from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Protocol
from uuid import UUID, uuid4

from vybe_core.models.evidence import Evidence


class LabOrderStatus(str, Enum):
    DRAFT = "draft"
    REQUIRES_REVIEW = "requires_review"
    AUTHORIZED = "authorized"
    ORDERED = "ordered"
    KIT_SHIPPED = "kit_shipped"
    SAMPLE_COLLECTED = "sample_collected"
    PROCESSING = "processing"
    PARTIAL_RESULTS = "partial_results"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    FAILED = "failed"


class LabCollectionMode(str, Enum):
    PATIENT_SERVICE_CENTER = "patient_service_center"
    AT_HOME = "at_home"
    MOBILE_PHLEBOTOMY = "mobile_phlebotomy"
    OTHER = "other"


@dataclass(frozen=True, slots=True)
class LabTestSelection:
    code: str
    display_name: str
    quantity: int = 1

    def __post_init__(self) -> None:
        if not self.code.strip() or not self.display_name.strip():
            raise ValueError("lab test code and display name are required")
        if self.quantity < 1:
            raise ValueError("lab test quantity must be positive")


@dataclass(frozen=True, slots=True)
class LabOrderRequest:
    person_id: UUID
    application_id: UUID
    tests: tuple[LabTestSelection, ...]
    collection_mode: LabCollectionMode
    created_at: datetime
    consent_reference: str
    external_patient_reference: str | None = None
    metadata: dict[str, str] = field(default_factory=dict)
    id: UUID = field(default_factory=uuid4)

    def __post_init__(self) -> None:
        if not self.tests:
            raise ValueError("at least one lab test must be selected")
        if self.created_at.tzinfo is None:
            raise ValueError("created_at must be timezone-aware")
        if not self.consent_reference.strip():
            raise ValueError("consent_reference is required")


@dataclass(frozen=True, slots=True)
class LabOrder:
    request_id: UUID
    provider: str
    external_order_id: str
    status: LabOrderStatus
    updated_at: datetime
    collection_mode: LabCollectionMode
    status_detail: str | None = None

    def __post_init__(self) -> None:
        if not self.provider.strip() or not self.external_order_id.strip():
            raise ValueError("provider and external_order_id are required")
        if self.updated_at.tzinfo is None:
            raise ValueError("updated_at must be timezone-aware")


@dataclass(frozen=True, slots=True)
class LabResultBatch:
    provider: str
    external_order_id: str
    received_at: datetime
    evidence: tuple[Evidence, ...]
    source_document_reference: str | None = None

    def __post_init__(self) -> None:
        if not self.provider.strip() or not self.external_order_id.strip():
            raise ValueError("provider and external_order_id are required")
        if self.received_at.tzinfo is None:
            raise ValueError("received_at must be timezone-aware")


class LabOrderingProvider(Protocol):
    """Commercial clinical-ordering boundary, separate from health stores.

    Implementations may use a physician network, diagnostic marketplace, direct
    lab relationship, or another approved infrastructure provider. HealthKit and
    Health Connect must never implement this protocol.
    """

    @property
    def provider_id(self) -> str: ...

    async def create_order(self, request: LabOrderRequest) -> LabOrder: ...

    async def get_order(self, external_order_id: str) -> LabOrder: ...

    async def cancel_order(self, external_order_id: str) -> LabOrder: ...

    async def fetch_results(self, external_order_id: str) -> LabResultBatch: ...
