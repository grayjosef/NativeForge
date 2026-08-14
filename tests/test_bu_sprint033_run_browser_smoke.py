"""Sprint 033: execute demo-runtime browser smoke."""

from __future__ import annotations

from nativeforge.services.nm_wa_browser_demo_contract_service import (
    validate_browser_run_id,
)
from nativeforge.services.nm_wa_browser_smoke_runner_service import (
    run_nm_wa_browser_demo_smoke,
)


def test_run_browser_smoke_pass() -> None:
    r = run_nm_wa_browser_demo_smoke()
    assert r["overall_status"] == "PASS"
    assert validate_browser_run_id(r["run_id"])
    assert r["playwright_status"] == "NOT_RUN"
    assert r["smoke_mode"] == "demo_runtime_static_vitest"
    assert r["failures"] == []
