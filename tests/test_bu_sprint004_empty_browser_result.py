"""Sprint 004: empty browser smoke result scaffold."""

from __future__ import annotations

from nativeforge.services.nm_wa_browser_demo_contract_service import (
    EXPECTED_SCREENS,
    empty_browser_smoke_result,
)


def test_empty_browser_result() -> None:
    r = empty_browser_smoke_result(status="NOT_RUN", not_run_reason="scaffold")
    assert len(r["screens"]) == len(EXPECTED_SCREENS)
    assert r["playwright_status"] == "NOT_RUN"
    assert r["prior_offline_smoke_run_id"].startswith("nf_os_smoke_")
