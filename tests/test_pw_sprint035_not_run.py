"""Sprint 035: honest NOT_RUN Playwright result."""

from __future__ import annotations

from nativeforge.services.nm_wa_playwright_e2e_contract_service import (
    validate_playwright_smoke_result,
)
from nativeforge.services.nm_wa_playwright_smoke_runner_service import (
    playwright_smoke_result_not_run,
)


def test_not_run() -> None:
    r = playwright_smoke_result_not_run("chromium_unavailable")
    assert r["overall_status"] == "NOT_RUN"
    assert r["run_id"] is None
    assert validate_playwright_smoke_result(r) == []
