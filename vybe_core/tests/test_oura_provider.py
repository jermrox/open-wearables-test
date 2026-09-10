from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from vybe_core.models.evidence import SourceType
from vybe_core.providers.contracts import SyncWindow
from vybe_core.providers.oura.adapter import OuraDataError, OuraProvider


NOW = datetime(2026, 9, 10, 18, 0, tzinfo=timezone.utc)


class FakeTokens:
    def __init__(self, token: str = "access-token") -> None:
        self.token = token
        self.calls: list[tuple[str, str]] = []

    async def get_access_token(self, *, provider: str, subject_id: str) -> str:
        self.calls.append((provider, subject_id))
        return self.token


class FakeHttp:
    def __init__(self, payload: dict) -> None:
        self.payload = payload
        self.calls: list[dict] = []

    async def get_json(self, *, url: str, headers=None, params=None):
        self.calls.append({"url": url, "headers": dict(headers or {}), "params": dict(params or {})})
        return self.payload


@pytest.mark.asyncio
async def test_heart_rate_request_and_normalization_match_v2_contract() -> None:
    http = FakeHttp(
        {
            "data": [
                {
                    "timestamp": "2026-09-10T12:35:00-04:00",
                    "timestamp_unix": 1789058100,
                    "bpm": 67,
                    "source": "awake",
                }
            ],
            "next_token": "page-2",
        }
    )
    tokens = FakeTokens()
    provider = OuraProvider(http=http, tokens=tokens, clock=lambda: NOW)
    window = SyncWindow(NOW - timedelta(hours=2), NOW)

    batch = await provider.collect_batch(
        subject_id="oura-user-1",
        stream="heart_rate",
        window=window,
        cursor="page-1",
    )

    assert tokens.calls == [("oura", "oura-user-1")]
    request = http.calls[0]
    assert request["url"] == "https://api.ouraring.com/v2/usercollection/heartrate"
    assert request["headers"] == {"Authorization": "Bearer access-token"}
    assert request["params"] == {
        "start_datetime": window.start.isoformat(),
        "end_datetime": window.end.isoformat(),
        "next_token": "page-1",
    }
    assert batch.next_cursor == "page-2"
    assert batch.has_more is True
    assert len(batch.evidence) == 1
    item = batch.evidence[0]
    assert item.metric == "heart_rate"
    assert item.value == 67
    assert item.unit == "bpm"
    assert item.recorded_at.isoformat() == "2026-09-10T12:35:00-04:00"
    assert item.source.source_type is SourceType.CLOUD_PROVIDER
    assert item.source.provider == "oura"
    assert item.source.source_record_id == "heartrate:1789058100"
    assert item.metadata == {"oura_source": "awake"}
    assert item.provenance.processor == "oura_v2_adapter"
    assert item.provenance.raw_sha256 is not None
    assert item.quality.confidence is None


@pytest.mark.asyncio
async def test_daily_steps_uses_date_query_and_provider_document_id() -> None:
    http = FakeHttp(
        {
            "data": [
                {
                    "id": "activity-doc-1",
                    "day": "2026-09-09",
                    "steps": 10432,
                    "timestamp": "2026-09-09T04:00:00+00:00",
                }
            ],
            "next_token": None,
        }
    )
    provider = OuraProvider(http=http, tokens=FakeTokens(), clock=lambda: NOW)
    window = SyncWindow(NOW - timedelta(days=2), NOW)

    batch = await provider.collect_batch(
        subject_id="oura-user-1",
        stream="steps",
        window=window,
        cursor=None,
    )

    assert http.calls[0]["url"] == "https://api.ouraring.com/v2/usercollection/daily_activity"
    assert http.calls[0]["params"] == {
        "start_date": window.start.date().isoformat(),
        "end_date": window.end.date().isoformat(),
    }
    item = batch.evidence[0]
    assert item.metric == "steps"
    assert item.value == 10432
    assert item.unit == "count"
    assert item.source.source_record_id == "activity-doc-1"
    assert item.metadata == {"day": "2026-09-09"}
    assert batch.has_more is False


@pytest.mark.asyncio
async def test_unknown_stream_fails_before_http_request() -> None:
    http = FakeHttp({"data": [], "next_token": None})
    provider = OuraProvider(http=http, tokens=FakeTokens(), clock=lambda: NOW)

    with pytest.raises(OuraDataError, match="unsupported Oura stream"):
        await provider.collect_batch(
            subject_id="oura-user-1",
            stream="sleep_magic",
            window=SyncWindow(NOW - timedelta(days=1), NOW),
            cursor=None,
        )
    assert http.calls == []


@pytest.mark.asyncio
async def test_malformed_required_row_fails_batch_instead_of_silently_dropping() -> None:
    provider = OuraProvider(
        http=FakeHttp(
            {
                "data": [{"timestamp": "not-a-timestamp", "bpm": 70, "source": "awake"}],
                "next_token": None,
            }
        ),
        tokens=FakeTokens(),
        clock=lambda: NOW,
    )

    with pytest.raises(OuraDataError, match="valid ISO-8601"):
        await provider.collect_batch(
            subject_id="oura-user-1",
            stream="heart_rate",
            window=SyncWindow(NOW - timedelta(days=1), NOW),
            cursor=None,
        )


@pytest.mark.asyncio
async def test_collect_iterates_next_tokens_without_exposing_pagination() -> None:
    class PagingHttp:
        async def get_json(self, *, url: str, headers=None, params=None):
            cursor = (params or {}).get("next_token")
            if cursor is None:
                return {
                    "data": [{"timestamp": "2026-09-10T16:00:00+00:00", "bpm": 65, "source": "awake"}],
                    "next_token": "next",
                }
            return {
                "data": [{"timestamp": "2026-09-10T16:05:00+00:00", "bpm": 66, "source": "awake"}],
                "next_token": None,
            }

    provider = OuraProvider(http=PagingHttp(), tokens=FakeTokens(), clock=lambda: NOW)
    items = [
        item
        async for item in provider.collect(
            "oura-user-1",
            "heart_rate",
            SyncWindow(NOW - timedelta(hours=3), NOW),
        )
    ]
    assert [item.value for item in items] == [65, 66]
