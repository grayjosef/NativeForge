"""Sprint 041: Playwright E2E closeout packet."""

from __future__ import annotations

from nativeforge.services.nm_wa_playwright_e2e_closeout_packet_service import (
    build_playwright_e2e_closeout_packet,
)
from nativeforge.services.nm_wa_playwright_smoke_runner_service import (
    run_playwright_nm_wa_smoke,
)


def test_closeout_packet() -> None:
    smoke = run_playwright_nm_wa_smoke(dry_run_skip_exec=True, simulated_exit_code=0)
    pkt = build_playwright_e2e_closeout_packet(
        head_before="a24650a",
        head_after="deadbeef",
        playwright_result=smoke,
        commits_created=["c1"],
        stash_status="stash@{0}: On main: wip-sprint8-ui-redesign-do-not-commit",
        uv_lock_status="present_untouched",
        package_dependency_changes="@playwright/test added to frontend package-lock only",
    )
    assert pkt["playwright_overall_status"] == "PASS"
    assert pkt["frontend_demo_route_changed"] is False
    assert len(pkt["screen_statuses"]) == 14
