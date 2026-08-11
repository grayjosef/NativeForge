"""Sprint 036: Playwright runner dry-run FAIL path."""

from __future__ import annotations

from nativeforge.services.nm_wa_playwright_smoke_runner_service import (
    run_playwright_nm_wa_smoke,
)


def test_runner_dry_fail() -> None:
    r = run_playwright_nm_wa_smoke(dry_run_skip_exec=True, simulated_exit_code=1)
    assert r["overall_status"] == "FAIL"
    assert r["failures"]
