"""Sprint 276-277: tier-1 dry fetch and idempotent upsert."""

from __future__ import annotations

from nativeforge.services.staging_tier1_dry_fetch_service import (
    reset_tier1_dry_fetch_rate_limit,
    run_tier1_dry_fetch_and_upsert,
    select_tier1_dry_fetch_source,
)


def test_select_one_tier1_source() -> None:
    source = select_tier1_dry_fetch_source()
    assert source["tier"] == 1


def test_idempotent_dry_fetch_path() -> None:
    reset_tier1_dry_fetch_rate_limit()
    result = run_tier1_dry_fetch_and_upsert()
    assert result["idempotent_path_verified"] is True
    assert result["second_run_zero_new"] is True
    assert result["no_bulk_crawl"] is True
