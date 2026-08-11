"""Sprint 034: Playwright runner dry-run PASS path."""

from __future__ import annotations

from nativeforge.services.nm_wa_playwright_e2e_contract_service import (
    validate_playwright_run_id,
)
from nativeforge.services.nm_wa_playwright_smoke_runner_service import (
    run_playwright_nm_wa_smoke,
)


def test_runner_dry_pass() -> None:
    r = run_playwright_nm_wa_smoke(dry_run_skip_exec=True, simulated_exit_code=0)
    assert r["overall_status"] == "PASS"
    assert validate_playwright_run_id(r["run_id"])
    assert r["smoke_mode"] == "playwright_e2e"
