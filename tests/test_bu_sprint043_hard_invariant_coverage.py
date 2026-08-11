"""Sprint 043: hard invariant coverage in browser closeout packet."""

from __future__ import annotations

from nativeforge.services.nm_wa_browser_demo_closeout_packet_service import (
    build_browser_demo_closeout_packet,
)
from nativeforge.services.nm_wa_browser_smoke_runner_service import (
    browser_smoke_result_not_run,
)


def test_hard_invariants() -> None:
    pkt = build_browser_demo_closeout_packet(
        head_before="a",
        head_after="b",
        browser_smoke_result=browser_smoke_result_not_run("n/a"),
        commits_created=[],
        stash_status="ok",
        uv_lock_status="ok",
    )
    assert "ui_demo_read_only_advisory" in pkt["hard_invariants_covered"]
    assert len(pkt["hard_invariants_covered"]) == 10
