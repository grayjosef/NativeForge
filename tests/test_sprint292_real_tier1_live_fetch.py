"""Sprint 292: real tier-1 live fetch."""

from __future__ import annotations

from nativeforge.services.real_tier1_live_fetch_service import (
    fixture_tier1_live_fetch,
    reset_real_tier1_fetch_rate_limit,
    run_real_tier1_fetch_and_upsert,
)


def test_real_tier1_idempotent() -> None:
    reset_real_tier1_fetch_rate_limit()
    result = run_real_tier1_fetch_and_upsert(
        fetcher=fixture_tier1_live_fetch,
        min_interval_seconds=0,
    )
    assert result["second_run_zero_new"] is True
    assert result["real_fetch"] is True
