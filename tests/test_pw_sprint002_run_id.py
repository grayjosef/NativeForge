"""Sprint 002: Playwright run_id format."""

from __future__ import annotations

from nativeforge.services.nm_wa_playwright_e2e_contract_service import (
    validate_playwright_run_id,
)


def test_playwright_run_id() -> None:
    assert validate_playwright_run_id("nf_os_playwright_20260811T123456Z_abcd1234")
    assert not validate_playwright_run_id("nf_os_browser_20260811T123456Z_abcd1234")
