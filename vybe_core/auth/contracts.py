from __future__ import annotations

from typing import Protocol
from uuid import UUID

from vybe_core.auth.models import ApiCredential, Application, Organization


class AuthStore(Protocol):
    """Persistence boundary for commercial organization/application identity."""

    async def put_organization(self, organization: Organization) -> None: ...

    async def put_application(self, application: Application) -> None: ...

    async def put_credential(self, credential: ApiCredential) -> None: ...

    async def get_application(self, application_id: UUID) -> Application | None: ...

    async def get_credential_by_prefix(self, key_prefix: str) -> ApiCredential | None: ...
