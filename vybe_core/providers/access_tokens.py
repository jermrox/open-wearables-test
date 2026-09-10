from __future__ import annotations

from typing import Protocol


class AccessTokenResolver(Protocol):
    """Resolve a usable provider access token for one provider subject.

    Implementations may use ProviderConnection + TokenVault + refresh lifecycle.
    Provider adapters depend only on this narrow interface and never access the
    vault, database, or refresh credentials directly.
    """

    async def get_access_token(self, *, provider: str, subject_id: str) -> str: ...
