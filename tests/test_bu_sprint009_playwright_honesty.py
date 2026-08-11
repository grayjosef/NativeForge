"""Sprint 009: Playwright unavailability documented honestly."""

from __future__ import annotations

from nativeforge.services.nm_wa_browser_demo_contract_service import (
    PLAYWRIGHT_AVAILABLE,
    PLAYWRIGHT_NOT_RUN_REASON,
    build_browser_demo_contract,
)


def test_playwright_honesty() -> None:
    assert PLAYWRIGHT_AVAILABLE is False
    assert "Playwright" in PLAYWRIGHT_NOT_RUN_REASON
    c = build_browser_demo_contract()
    assert c["playwright_available"] is False
