"""Sprint 039: runner keeps Playwright status NOT_RUN with reason."""

from __future__ import annotations

from nativeforge.services.nm_wa_browser_smoke_runner_service import (
    run_nm_wa_browser_demo_smoke,
)


def test_playwright_not_run_in_pass_result() -> None:
    r = run_nm_wa_browser_demo_smoke()
    assert r["overall_status"] == "PASS"
    assert r["playwright_status"] == "NOT_RUN"
    assert "Playwright" in r["playwright_not_run_reason"]
