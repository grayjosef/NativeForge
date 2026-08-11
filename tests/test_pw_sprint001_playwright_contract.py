"""Sprint 001: Playwright E2E contract."""

from __future__ import annotations

from nativeforge.services.nm_wa_playwright_e2e_contract_service import (
    EXPECTED_SCREENS,
    build_playwright_e2e_contract,
)


def test_playwright_contract() -> None:
    c = build_playwright_e2e_contract()
    assert c["smoke_mode"] == "playwright_e2e"
    assert c["distinguishes_from_demo_runtime"] is True
    assert c["uv_lock_must_remain_untouched"] is True
    assert c["demo_route_path"] == "/?view=nm_wa_operator_demo"
    assert len(c["expected_screens"]) == len(EXPECTED_SCREENS)
