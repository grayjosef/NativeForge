"""Sprint 043: hard invariant coverage in closeout packet."""

from __future__ import annotations

from nativeforge.services.nm_wa_smoke_closeout_packet_service import (
    build_smoke_closeout_packet,
)
from nativeforge.services.nm_wa_smoke_runner_service import smoke_result_not_run


def test_hard_invariant_list() -> None:
    pkt = build_smoke_closeout_packet(
        head_before="a",
        head_after="b",
        smoke_result=smoke_result_not_run("n/a"),
        commits_created=[],
        stash_status="ok",
        uv_lock_status="ok",
    )
    assert "honest_pass_fail_not_run" in pkt["hard_invariants_covered"]
    assert "no_fabricated_run_id" in pkt["hard_invariants_covered"]
    assert len(pkt["hard_invariants_covered"]) == 9
