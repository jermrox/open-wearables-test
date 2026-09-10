from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from vybe_core.access.policy import DataScope, DeveloperGrant
from vybe_core.auth.credentials import CredentialVerificationError, verify_credential
from vybe_core.auth.models import ApiCredential
from vybe_core.storage.postgres_auth import AuthStore


@dataclass(frozen=True, slots=True)
class AuthenticatedApplication:
    application_id: object
    credential_id: object
    grant: DeveloperGrant


async def authenticate_api_key(
    *,
    presented_key: str,
    now: datetime,
    auth_store: AuthStore,
    required_scope: DataScope | None = None,
) -> AuthenticatedApplication:
    """Resolve by non-secret prefix, then verify the secret hash in constant time."""

    prefix, separator, _secret = presented_key.partition(".")
    if not separator or not prefix:
        raise CredentialVerificationError("malformed credential")

    credential: ApiCredential | None = await auth_store.get_credential_by_prefix(prefix)
    if credential is None:
        # Deliberately use the same public error family as bad secrets; callers
        # should not reveal whether a credential prefix exists.
        raise CredentialVerificationError("invalid credential")

    verify_credential(
        credential=credential,
        presented_key=presented_key,
        now=now,
        required_scope=required_scope.value if required_scope is not None else None,
    )

    scopes: set[DataScope] = set()
    for raw_scope in credential.scopes:
        try:
            scopes.add(DataScope(raw_scope))
        except ValueError:
            # Unknown future/internal scopes do not become public permissions.
            continue

    return AuthenticatedApplication(
        application_id=credential.application_id,
        credential_id=credential.id,
        grant=DeveloperGrant(
            developer_id=f"credential:{credential.id}",
            scopes=frozenset(scopes),
        ),
    )
