"""Sprint 041: browser demo closeout packet."""

from __future__ import annotations

from nativeforge.services.nm_wa_browser_demo_closeout_packet_service import (
    build_browser_demo_closeout_packet,
)
from nativeforge.services.nm_wa_browser_smoke_runner_service import (
    run_nm_wa_browser_demo_smoke,
)


def test_closeout_packet() -> None:
    smoke = run_nm_wa_browser_demo_smoke()
    pkt = build_browser_demo_closeout_packet(
        head_before="0d50bf6",
        head_after="deadbeef",
        browser_smoke_result=smoke,
        commits_created=["c1"],
        stash_status="stash@{0}: On main: wip-sprint8-ui-redesign-do-not-commit",
        uv_lock_status="present_untouched",
    )
    assert pkt["browser_overall_status"] == "PASS"
    assert pkt["playwright_status"] == "NOT_RUN"
    assert pkt["auth_human_gates_changed"] is False
    assert len(pkt["screen_statuses"]) == 14
