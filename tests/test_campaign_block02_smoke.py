"""Tests for Campaign Block 02 smoke."""

from __future__ import annotations

from nativeforge.services.campaign_block02_smoke_runner_service import (
    run_campaign_block02_smoke,
)


def test_campaign_block02_smoke_pass() -> None:
    result = run_campaign_block02_smoke()
    assert result["status"] == "PASS"
    assert result["failed_surfaces"] == []
