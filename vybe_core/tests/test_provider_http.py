from __future__ import annotations

import httpx
import pytest

from vybe_core.providers.http import HttpxJsonClient, ProviderHttpError


@pytest.mark.asyncio
async def test_http_client_returns_json_object() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"data": []}, request=request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        payload = await HttpxJsonClient(client).get_json(url="https://provider.test/data")
    assert payload == {"data": []}


@pytest.mark.asyncio
async def test_http_client_captures_numeric_retry_after() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, headers={"Retry-After": "12"}, request=request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(ProviderHttpError) as caught:
            await HttpxJsonClient(client).get_json(url="https://provider.test/data")

    assert caught.value.status_code == 429
    assert caught.value.retry_after_seconds == 12.0


@pytest.mark.asyncio
async def test_http_client_rejects_non_object_json_root() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=[{"bad": "shape"}], request=request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(ProviderHttpError, match="root must be an object"):
            await HttpxJsonClient(client).get_json(url="https://provider.test/data")
