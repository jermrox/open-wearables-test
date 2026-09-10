from __future__ import annotations

from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
import json
from typing import Any

from vybe_core.models.evidence import Evidence, EvidenceProvenance, EvidenceSource, SourceType
from vybe_core.providers.access_tokens import AccessTokenResolver
from vybe_core.providers.contracts import DeliveryMode, EvidenceProvider, ProviderCapabilities, SyncWindow
from vybe_core.providers.http import JsonHttpClient
from vybe_core.providers.sync import ProviderBatch


OURA_API_BASE = "https://api.ouraring.com/v2/usercollection"


class OuraDataError(ValueError):
    """Raised when an Oura response does not match the verified V2 contract."""


@dataclass(frozen=True, slots=True)
class OuraStream:
    endpoint: str
    metric: str
    unit: str
    datetime_query: bool


STREAMS: dict[str, OuraStream] = {
    "heart_rate": OuraStream(
        endpoint="heartrate",
        metric="heart_rate",
        unit="bpm",
        datetime_query=True,
    ),
    "steps": OuraStream(
        endpoint="daily_activity",
        metric="steps",
        unit="count",
        datetime_query=False,
    ),
}


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _parse_timestamp(value: Any, *, field: str) -> datetime:
    if not isinstance(value, str) or not value.strip():
        raise OuraDataError(f"Oura field {field} must be a non-empty timestamp string")
    normalized = value.strip()
    if normalized.endswith("Z"):
        normalized = normalized[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise OuraDataError(f"Oura field {field} is not a valid ISO-8601 timestamp") from exc
    if parsed.tzinfo is None:
        raise OuraDataError(f"Oura field {field} must include a timezone")
    return parsed


def _row_hash(row: dict[str, Any]) -> str:
    encoded = json.dumps(row, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return sha256(encoded).hexdigest()


def _response_data(payload: dict[str, Any]) -> tuple[list[dict[str, Any]], str | None]:
    data = payload.get("data")
    if not isinstance(data, list):
        raise OuraDataError("Oura response data must be an array")
    rows: list[dict[str, Any]] = []
    for row in data:
        if not isinstance(row, dict):
            raise OuraDataError("Oura response data rows must be objects")
        rows.append(row)
    next_token = payload.get("next_token")
    if next_token is not None and not isinstance(next_token, str):
        raise OuraDataError("Oura next_token must be a string or null")
    return rows, next_token


class OuraProvider(EvidenceProvider):
    """Oura API V2 adapter emitting canonical Vybe Evidence.

    Only streams with a currently verified source timestamp and value schema are
    implemented here. Additional Oura collections should be added only after
    their timestamp semantics are explicitly modeled and tested.
    """

    def __init__(
        self,
        *,
        http: JsonHttpClient,
        tokens: AccessTokenResolver,
        clock: Callable[[], datetime] = _utcnow,
    ) -> None:
        self._http = http
        self._tokens = tokens
        self._clock = clock

    @property
    def provider_id(self) -> str:
        return "oura"

    @property
    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            delivery_modes=frozenset({DeliveryMode.REST_PULL, DeliveryMode.WEBHOOK}),
            supports_historical_sync=True,
            supports_live_sync=True,
        )

    async def collect(
        self,
        subject_id: str,
        stream: str,
        window: SyncWindow,
    ) -> AsyncIterator[Evidence]:
        cursor: str | None = None
        while True:
            batch = await self.collect_batch(
                subject_id=subject_id,
                stream=stream,
                window=window,
                cursor=cursor,
            )
            for item in batch.evidence:
                yield item
            if not batch.has_more:
                return
            if batch.next_cursor is None:
                raise OuraDataError("Oura returned additional pages without next_token")
            cursor = batch.next_cursor

    async def collect_batch(
        self,
        *,
        subject_id: str,
        stream: str,
        window: SyncWindow,
        cursor: str | None,
    ) -> ProviderBatch:
        definition = STREAMS.get(stream)
        if definition is None:
            raise OuraDataError(f"unsupported Oura stream: {stream}")

        access_token = await self._tokens.get_access_token(provider=self.provider_id, subject_id=subject_id)
        if not access_token:
            raise OuraDataError("Oura access token resolver returned an empty token")

        params: dict[str, str] = {}
        if definition.datetime_query:
            params["start_datetime"] = window.start.isoformat()
            params["end_datetime"] = window.end.isoformat()
        else:
            params["start_date"] = window.start.date().isoformat()
            params["end_date"] = window.end.date().isoformat()
        if cursor is not None:
            params["next_token"] = cursor

        payload = await self._http.get_json(
            url=f"{OURA_API_BASE}/{definition.endpoint}",
            headers={"Authorization": f"Bearer {access_token}"},
            params=params,
        )
        rows, next_token = _response_data(payload)
        ingested_at = self._clock()
        if ingested_at.tzinfo is None:
            raise OuraDataError("Oura adapter clock must return a timezone-aware datetime")

        evidence = tuple(self._normalize_row(stream, row, ingested_at=ingested_at) for row in rows)
        batch_hash = sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        ).hexdigest()
        return ProviderBatch(
            evidence=evidence,
            next_cursor=next_token,
            has_more=next_token is not None,
            source_batch_id=f"oura:{stream}:{batch_hash}",
        )

    def _normalize_row(self, stream: str, row: dict[str, Any], *, ingested_at: datetime) -> Evidence:
        if stream == "heart_rate":
            timestamp = _parse_timestamp(row.get("timestamp"), field="timestamp")
            bpm = row.get("bpm")
            if not isinstance(bpm, (int, float)) or isinstance(bpm, bool):
                raise OuraDataError("Oura heart-rate bpm must be numeric")
            source = row.get("source")
            if source is not None and not isinstance(source, str):
                raise OuraDataError("Oura heart-rate source must be a string or null")
            source_record_id = f"heartrate:{row.get('timestamp_unix', row['timestamp'])}"
            metadata = {"oura_source": source} if source is not None else {}
            value = bpm
            metric = "heart_rate"
            unit = "bpm"
        elif stream == "steps":
            timestamp = _parse_timestamp(row.get("timestamp"), field="timestamp")
            steps = row.get("steps")
            if not isinstance(steps, (int, float)) or isinstance(steps, bool):
                raise OuraDataError("Oura daily-activity steps must be numeric")
            document_id = row.get("id")
            if not isinstance(document_id, str) or not document_id:
                raise OuraDataError("Oura daily-activity id must be a non-empty string")
            source_record_id = document_id
            metadata = {"day": row.get("day")} if row.get("day") is not None else {}
            value = steps
            metric = "steps"
            unit = "count"
        else:
            raise OuraDataError(f"unsupported Oura stream: {stream}")

        return Evidence(
            metric=metric,
            value=value,
            unit=unit,
            recorded_at=timestamp,
            source=EvidenceSource(
                source_type=SourceType.CLOUD_PROVIDER,
                provider=self.provider_id,
                source_record_id=source_record_id,
            ),
            provenance=EvidenceProvenance(
                ingested_at=ingested_at,
                processor="oura_v2_adapter",
                processing_version="1.0.0",
                raw_sha256=_row_hash(row),
            ),
            metadata=metadata,
        )
