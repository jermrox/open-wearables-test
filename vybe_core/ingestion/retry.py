from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from enum import Enum


class FailureDisposition(str, Enum):
    RETRYABLE = "retryable"
    TERMINAL = "terminal"


@dataclass(frozen=True, slots=True)
class RetryPolicy:
    max_attempts: int = 5
    initial_delay: timedelta = timedelta(seconds=2)
    multiplier: float = 2.0
    max_delay: timedelta = timedelta(minutes=5)

    def __post_init__(self) -> None:
        if self.max_attempts < 1:
            raise ValueError("max_attempts must be at least 1")
        if self.initial_delay.total_seconds() <= 0:
            raise ValueError("initial_delay must be positive")
        if self.multiplier < 1.0:
            raise ValueError("multiplier must be at least 1.0")
        if self.max_delay < self.initial_delay:
            raise ValueError("max_delay must be >= initial_delay")

    def delay_for_attempt(self, attempt: int) -> timedelta:
        if attempt < 1:
            raise ValueError("attempt numbers start at 1")
        seconds = self.initial_delay.total_seconds() * (self.multiplier ** (attempt - 1))
        return min(timedelta(seconds=seconds), self.max_delay)


@dataclass(frozen=True, slots=True)
class FailureRecord:
    operation: str
    provider: str
    disposition: FailureDisposition
    attempt: int
    error_type: str
    error_message: str
    retry_after: timedelta | None = None

    def __post_init__(self) -> None:
        if not self.operation.strip() or not self.provider.strip():
            raise ValueError("operation and provider are required")
        if self.attempt < 1:
            raise ValueError("attempt must be at least 1")
        if self.disposition is FailureDisposition.TERMINAL and self.retry_after is not None:
            raise ValueError("terminal failures cannot have retry_after")
