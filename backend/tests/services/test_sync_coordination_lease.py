"""Lease renewal for the pull primary lock: a killed worker stops renewing and the lock frees."""

from unittest.mock import patch
from uuid import uuid4

import pytest

from app.config import Settings, settings
from app.integrations.redis_client import get_redis_client
from app.services import sync_coordination
from app.services.sync_coordination import (
    bind_primary_lease,
    clear_primary_lease,
    lease_lost,
    release_primary,
    renew_if_due,
    renew_primary,
    try_become_primary,
)

PROVIDER = "google"
PROVIDER_USER_ID = "4661043890044766408"


@pytest.fixture(autouse=True)
def _clean_lease():
    clear_primary_lease()
    yield
    clear_primary_lease()


@pytest.fixture
def redis_client():
    return get_redis_client()


class TestLeaseTtl:
    def test_pull_scope_uses_the_short_lease(self) -> None:
        assert sync_coordination._ttl_for("pull") == settings.linked_sync_pull_lease_seconds
        assert sync_coordination._ttl_for("backfill") == settings.linked_sync_backfill_lease_seconds
        assert sync_coordination._ttl_for("pull") < sync_coordination._ttl_for("backfill")

    def test_acquired_pull_lock_carries_the_lease_ttl(self, redis_client) -> None:
        acquired, token, _ = try_become_primary(PROVIDER, PROVIDER_USER_ID, uuid4(), scope="pull")
        assert acquired
        key = sync_coordination._primary_key(PROVIDER, PROVIDER_USER_ID, "pull")
        assert 0 < redis_client.ttl(key) <= settings.linked_sync_pull_lease_seconds


class TestRenewPrimary:
    def test_renew_extends_only_our_own_lease(self, redis_client) -> None:
        user_id = uuid4()
        _, token, _ = try_become_primary(PROVIDER, PROVIDER_USER_ID, user_id, scope="pull")
        key = sync_coordination._primary_key(PROVIDER, PROVIDER_USER_ID, "pull")
        redis_client.expire(key, 5)

        assert renew_primary(PROVIDER, PROVIDER_USER_ID, user_id, token, scope="pull") is True
        assert redis_client.ttl(key) > 5

    def test_renew_fails_once_another_profile_holds_it(self) -> None:
        user_id, token = uuid4(), "stale-token"
        try_become_primary(PROVIDER, PROVIDER_USER_ID, uuid4(), scope="pull")

        assert renew_primary(PROVIDER, PROVIDER_USER_ID, user_id, token, scope="pull") is False

    def test_renew_fails_when_the_lease_already_expired(self) -> None:
        user_id, token = uuid4(), "gone"

        assert renew_primary(PROVIDER, PROVIDER_USER_ID, user_id, token, scope="pull") is False


class TestRenewIfDue:
    def test_no_op_without_a_bound_lease(self) -> None:
        with patch.object(sync_coordination, "renew_primary") as renew:
            renew_if_due()
        renew.assert_not_called()
        assert lease_lost() is False

    def test_no_op_when_not_primary(self) -> None:
        bind_primary_lease(PROVIDER, PROVIDER_USER_ID, uuid4(), "")
        with patch.object(sync_coordination, "renew_primary") as renew:
            renew_if_due()
        renew.assert_not_called()

    def test_throttled_until_the_interval_elapses(self) -> None:
        bind_primary_lease(PROVIDER, PROVIDER_USER_ID, uuid4(), "tok")
        with patch.object(sync_coordination, "renew_primary", return_value=True) as renew:
            renew_if_due()
            renew.assert_not_called()

            sync_coordination._lease.state.last -= settings.linked_sync_renew_interval_seconds + 1
            renew_if_due()
            renew.assert_called_once()

    def test_marks_the_lease_lost_and_stops_renewing(self) -> None:
        bind_primary_lease(PROVIDER, PROVIDER_USER_ID, uuid4(), "tok")
        sync_coordination._lease.state.last -= settings.linked_sync_renew_interval_seconds + 1

        with patch.object(sync_coordination, "renew_primary", return_value=False) as renew:
            renew_if_due()
            assert lease_lost() is True

            sync_coordination._lease.state.last -= settings.linked_sync_renew_interval_seconds + 1
            renew_if_due()
            renew.assert_called_once()  # a lost lease is never renewed again

    def test_lease_is_per_thread(self) -> None:
        from concurrent.futures import ThreadPoolExecutor

        bind_primary_lease(PROVIDER, PROVIDER_USER_ID, uuid4(), "tok")
        with ThreadPoolExecutor(max_workers=1) as pool:
            assert pool.submit(lease_lost).result() is False  # other thread sees no lease
        assert sync_coordination._lease.state is not None


class TestReleaseAfterLeaseLoss:
    def test_a_demoted_holder_cannot_release_the_successor_lock(self, redis_client) -> None:
        first, second = uuid4(), uuid4()
        _, first_token, _ = try_become_primary(PROVIDER, PROVIDER_USER_ID, first, scope="pull")
        key = sync_coordination._primary_key(PROVIDER, PROVIDER_USER_ID, "pull")
        redis_client.delete(key)  # first holder's lease lapses
        acquired, _, _ = try_become_primary(PROVIDER, PROVIDER_USER_ID, second, scope="pull")
        assert acquired

        assert release_primary(PROVIDER, PROVIDER_USER_ID, first, first_token, scope="pull") is False
        assert redis_client.exists(key)


class TestSettingsInvariant:
    """The lease must outlive the longest silence between two renewals."""

    def test_lease_shorter_than_the_worst_retry_gap_is_rejected(self) -> None:
        with pytest.raises(ValueError, match="worst gap between lease renewals"):
            Settings(linked_sync_pull_lease_seconds=60)

    def test_renew_interval_longer_than_the_lease_is_rejected(self) -> None:
        with pytest.raises(ValueError, match="must be shorter than"):
            Settings(linked_sync_renew_interval_seconds=200)

    def test_raising_retries_without_the_lease_is_rejected(self) -> None:
        with pytest.raises(ValueError, match="worst gap between lease renewals"):
            Settings(provider_max_retries=5)

    def test_defaults_leave_headroom(self) -> None:
        worst_gap = settings.provider_request_timeout_seconds + settings.provider_retry_base_delay_seconds * 2 ** (
            settings.provider_max_retries - 1
        )
        assert worst_gap < settings.linked_sync_pull_lease_seconds
