"""Sprint 004: empty Playwright smoke result scaffold."""

from __future__ import annotations

from nativeforge.services.nm_wa_playwright_e2e_contract_service import (
    EXPECTED_SCREENS,
    empty_playwright_smoke_result,
)


def test_empty_result() -> None:
    r = empty_playwright_smoke_result(status="NOT_RUN", not_run_reason="scaffold")
    assert len(r["screens"]) == len(EXPECTED_SCREENS)
    assert r["prior_demo_runtime_run_id"].startswith("nf_os_browser_")
