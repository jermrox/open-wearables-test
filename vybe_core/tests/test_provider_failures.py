from datetime import timedelta

from vybe_core.ingestion.retry import FailureDisposition, RetryPolicy
from vybe_core.providers.failures import classify_provider_failure
from vybe_core.providers.http import ProviderHttpError


def classify(error: Exception, attempt: int = 1):
    return classify_provider_failure(
        provider="oura",
        operation="sync:heart_rate",
        attempt=attempt,
        error=error,
        retry_policy=RetryPolicy(initial_delay=timedelta(seconds=2), multiplier=2, max_delay=timedelta(seconds=30)),
    )


def test_401_requires_reauthentication() -> None:
    record = classify(ProviderHttpError(401, "expired"))
    assert record.disposition is FailureDisposition.REAUTH_REQUIRED
    assert record.retry_after is None


def test_403_requires_user_action_not_blind_retry() -> None:
    record = classify(ProviderHttpError(403, "forbidden"))
    assert record.disposition is FailureDisposition.USER_ACTION_REQUIRED
    assert record.retry_after is None


def test_429_honors_provider_retry_after() -> None:
    record = classify(ProviderHttpError(429, "rate limited", retry_after_seconds=17))
    assert record.disposition is FailureDisposition.RETRYABLE
    assert record.retry_after == timedelta(seconds=17)


def test_5xx_uses_bounded_retry_policy() -> None:
    record = classify(ProviderHttpError(503, "unavailable"), attempt=3)
    assert record.disposition is FailureDisposition.RETRYABLE
    assert record.retry_after == timedelta(seconds=8)


def test_transport_failure_is_retryable() -> None:
    record = classify(ProviderHttpError(0, "transport failure"))
    assert record.disposition is FailureDisposition.RETRYABLE


def test_schema_or_other_non_http_error_is_terminal() -> None:
    record = classify(ValueError("schema changed"))
    assert record.disposition is FailureDisposition.TERMINAL
    assert record.retry_after is None
