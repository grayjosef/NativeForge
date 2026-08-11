"""Sprint 034: honest NOT_RUN browser smoke result."""

from __future__ import annotations

from nativeforge.services.nm_wa_browser_demo_contract_service import (
    validate_browser_smoke_result,
)
from nativeforge.services.nm_wa_browser_smoke_runner_service import (
    browser_smoke_result_not_run,
)


def test_browser_not_run() -> None:
    r = browser_smoke_result_not_run("playwright_unavailable")
    assert r["overall_status"] == "NOT_RUN"
    assert r["run_id"] is None
    assert validate_browser_smoke_result(r) == []
