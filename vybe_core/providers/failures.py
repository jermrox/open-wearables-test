from __future__ import annotations

from datetime import timedelta

from vybe_core.ingestion.retry import FailureDisposition, FailureRecord, RetryPolicy
from vybe_core.providers.http import ProviderHttpError


def classify_provider_failure(
    *,
    provider: str,
    operation: str,
    attempt: int,
    error: Exception,
    retry_policy: RetryPolicy | None = None,
) -> FailureRecord:
    """Map provider failures into explicit operational outcomes.

    HTTP semantics intentionally remain conservative:
    - transport/timeout (status 0), 408, 409, 425, 429 and 5xx are retryable;
    - 401 requires reauthentication/token repair;
    - 403 requires user/operator action because it may represent consent,
      provider permissions, subscription state, or account eligibility;
    - other client/schema errors are terminal for the current operation.
    """

    policy = retry_policy or RetryPolicy()

    if isinstance(error, ProviderHttpError):
        status = error.status_code
        if status == 401:
            disposition = FailureDisposition.REAUTH_REQUIRED
            retry_after = None
        elif status == 403:
            disposition = FailureDisposition.USER_ACTION_REQUIRED
            retry_after = None
        elif status == 0 or status in {408, 409, 425, 429} or 500 <= status <= 599:
            disposition = FailureDisposition.RETRYABLE
            if error.retry_after_seconds is not None:
                retry_after = timedelta(seconds=error.retry_after_seconds)
            else:
                retry_after = policy.delay_for_attempt(attempt)
        else:
            disposition = FailureDisposition.TERMINAL
            retry_after = None
    else:
        disposition = FailureDisposition.TERMINAL
        retry_after = None

    return FailureRecord(
        operation=operation,
        provider=provider,
        disposition=disposition,
        attempt=attempt,
        error_type=type(error).__name__,
        error_message=str(error),
        retry_after=retry_after,
    )
