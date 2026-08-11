"""Sprint 041: smoke closeout packet."""

from __future__ import annotations

from nativeforge.services.nm_wa_smoke_closeout_packet_service import (
    build_smoke_closeout_packet,
)
from nativeforge.services.nm_wa_smoke_runner_service import (
    run_nm_wa_operator_surfacing_smoke,
)


def test_closeout_packet() -> None:
    smoke = run_nm_wa_operator_surfacing_smoke()
    pkt = build_smoke_closeout_packet(
        head_before="5abd356",
        head_after="deadbeef",
        smoke_result=smoke,
        commits_created=["c1"],
        stash_status="stash@{0}: On main: wip-sprint8-ui-redesign-do-not-commit",
        uv_lock_status="present_untouched",
    )
    assert pkt["smoke_overall_status"] == "PASS"
    assert pkt["smoke_run_id"] == smoke["run_id"]
    assert pkt["scoring_match_logic_changed"] is False
    assert len(pkt["surface_statuses"]) == 14
