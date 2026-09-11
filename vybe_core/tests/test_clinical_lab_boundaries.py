from datetime import datetime, timezone
from uuid import uuid4

import pytest

from vybe_core.clinical.labs import LabCollectionMode, LabOrderRequest, LabTestSelection
from vybe_core.health_store.contracts import HealthStoreCapabilityError, reject_clinical_ordering


NOW = datetime(2026, 9, 10, 20, 0, tzinfo=timezone.utc)


def test_lab_order_requires_explicit_consent_reference_and_selected_tests() -> None:
    request = LabOrderRequest(
        person_id=uuid4(),
        application_id=uuid4(),
        tests=(LabTestSelection(code="LDL", display_name="LDL Cholesterol"),),
        collection_mode=LabCollectionMode.PATIENT_SERVICE_CENTER,
        created_at=NOW,
        consent_reference="consent-123",
    )
    assert request.tests[0].code == "LDL"

    with pytest.raises(ValueError, match="consent_reference"):
        LabOrderRequest(
            person_id=uuid4(),
            application_id=uuid4(),
            tests=(LabTestSelection(code="A1C", display_name="Hemoglobin A1c"),),
            collection_mode=LabCollectionMode.AT_HOME,
            created_at=NOW,
            consent_reference="",
        )


def test_health_stores_cannot_be_used_as_lab_ordering_backends() -> None:
    with pytest.raises(HealthStoreCapabilityError, match="cannot place clinical or laboratory orders"):
        reject_clinical_ordering("apple_healthkit")

    with pytest.raises(HealthStoreCapabilityError, match="cannot place clinical or laboratory orders"):
        reject_clinical_ordering("health_connect")
