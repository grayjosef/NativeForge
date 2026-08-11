"""Sprint 037: Playwright result distinguishes from demo-runtime mode."""

from __future__ import annotations

from nativeforge.services.nm_wa_playwright_smoke_runner_service import (
    run_playwright_nm_wa_smoke,
)


def test_mode_distinct() -> None:
    r = run_playwright_nm_wa_smoke(dry_run_skip_exec=True, simulated_exit_code=0)
    assert r["smoke_mode"] == "playwright_e2e"
    assert r["prior_demo_runtime_run_id"].startswith("nf_os_browser_")
