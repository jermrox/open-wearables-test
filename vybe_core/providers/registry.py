from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

from vybe_core.providers.contracts import DeliveryMode, EvidenceProvider, SyncWindow


class ProviderRegistryError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class RegisteredProvider:
    provider: EvidenceProvider

    @property
    def provider_id(self) -> str:
        return self.provider.provider_id


class ProviderRegistry:
    """Runtime registry for provider adapters.

    Registration is explicit and duplicate provider IDs are rejected. The core
    depends on provider contracts rather than importing individual vendors.
    """

    def __init__(self) -> None:
        self._providers: dict[str, EvidenceProvider] = {}

    def register(self, provider: EvidenceProvider) -> None:
        provider_id = provider.provider_id.strip().lower()
        if not provider_id:
            raise ProviderRegistryError("provider_id must not be empty")
        if provider_id in self._providers:
            raise ProviderRegistryError(f"provider already registered: {provider_id}")
        self._providers[provider_id] = provider

    def get(self, provider_id: str) -> EvidenceProvider:
        key = provider_id.strip().lower()
        try:
            return self._providers[key]
        except KeyError as exc:
            raise ProviderRegistryError(f"unknown provider: {provider_id}") from exc

    def all(self) -> tuple[EvidenceProvider, ...]:
        return tuple(self._providers[key] for key in sorted(self._providers))

    def validate_window(self, provider_id: str, window: SyncWindow, *, stream: str | None = None) -> None:
        provider = self.get(provider_id)
        maximum_days = (
            provider.stream_capabilities(stream).max_historical_days
            if stream is not None
            else provider.capabilities.max_historical_days
        )
        if maximum_days is None:
            return
        if window.end - window.start > timedelta(days=maximum_days):
            target = f"{provider.provider_id}:{stream}" if stream is not None else provider.provider_id
            raise ProviderRegistryError(
                f"{target} supports at most {maximum_days} historical days per request"
            )

    def require_delivery_mode(
        self,
        provider_id: str,
        mode: DeliveryMode,
        *,
        stream: str | None = None,
    ) -> None:
        provider = self.get(provider_id)
        modes = (
            provider.stream_capabilities(stream).delivery_modes
            if stream is not None
            else provider.capabilities.delivery_modes
        )
        if mode not in modes:
            target = f"{provider.provider_id}:{stream}" if stream is not None else provider.provider_id
            raise ProviderRegistryError(
                f"{target} does not support delivery mode {mode.value}"
            )
