"""Sprint 006: Playwright E2E manifest."""

from __future__ import annotations

from nativeforge.services.nm_wa_playwright_e2e_contract_service import EXPECTED_SCREENS
from nativeforge.services.nm_wa_playwright_e2e_manifest_service import (
    build_playwright_e2e_manifest,
)


def test_manifest() -> None:
    m = build_playwright_e2e_manifest()
    assert m["expected_screens"] == list(EXPECTED_SCREENS)
    assert "playwright_not_installed_or_unrunnable" in m["hard_stops"]
