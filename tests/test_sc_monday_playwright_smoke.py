"""Tests: SC Monday Playwright runner contract (no browser exec in unit test)."""

from __future__ import annotations

from nativeforge.services.sc_monday_playwright_smoke_runner_service import (
    DEMO_ROUTE_PATH,
    EXPECTED_SCREENS,
    generate_sc_playwright_run_id,
    run_playwright_sc_monday_smoke,
)


def test_sc_playwright_run_id_prefix() -> None:
    rid = generate_sc_playwright_run_id()
    assert rid.startswith("nf_sc_monday_playwright_")


def test_sc_playwright_dry_run_not_fake_pass() -> None:
    result = run_playwright_sc_monday_smoke(dry_run_skip_exec=True)
    assert result["overall_status"] == "NOT_RUN"
    assert result["demo_route_path"] == DEMO_ROUTE_PATH
    assert len(result["surfaces"]) == len(EXPECTED_SCREENS)
    assert all(s["status"] == "NOT_RUN" for s in result["surfaces"])
