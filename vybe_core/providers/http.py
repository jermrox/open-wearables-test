from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Protocol

import httpx


@dataclass(frozen=True, slots=True)
class ProviderHttpError(RuntimeError):
    status_code: int
    message: str
    retry_after_seconds: float | None = None

    def __str__(self) -> str:
        return f"provider HTTP {self.status_code}: {self.message}"


class JsonHttpClient(Protocol):
    async def get_json(
        self,
        *,
        url: str,
        headers: Mapping[str, str] | None = None,
        params: Mapping[str, str] | None = None,
    ) -> dict[str, Any]: ...


class HttpxJsonClient(JsonHttpClient):
    """Thin provider HTTP adapter around a caller-owned AsyncClient.

    Client lifecycle, connection pooling, TLS configuration, proxies, and
    deployment-specific timeouts remain with the application composition root.
    """

    def __init__(self, client: httpx.AsyncClient) -> None:
        self._client = client

    async def get_json(
        self,
        *,
        url: str,
        headers: Mapping[str, str] | None = None,
        params: Mapping[str, str] | None = None,
    ) -> dict[str, Any]:
        try:
            response = await self._client.get(url, headers=headers, params=params)
        except httpx.TimeoutException as exc:
            raise ProviderHttpError(0, "request timed out") from exc
        except httpx.TransportError as exc:
            raise ProviderHttpError(0, "transport failure") from exc

        if response.is_error:
            retry_after: float | None = None
            raw_retry_after = response.headers.get("retry-after")
            if raw_retry_after is not None:
                try:
                    retry_after = max(0.0, float(raw_retry_after))
                except ValueError:
                    retry_after = None
            raise ProviderHttpError(
                status_code=response.status_code,
                message="provider request failed",
                retry_after_seconds=retry_after,
            )

        try:
            payload = response.json()
        except ValueError as exc:
            raise ProviderHttpError(response.status_code, "provider returned invalid JSON") from exc
        if not isinstance(payload, dict):
            raise ProviderHttpError(response.status_code, "provider JSON root must be an object")
        return payload
