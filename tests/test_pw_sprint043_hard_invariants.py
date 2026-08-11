"""Sprint 043: hard invariant coverage in Playwright closeout."""

from __future__ import annotations

from nativeforge.services.nm_wa_playwright_e2e_closeout_packet_service import (
    build_playwright_e2e_closeout_packet,
)
from nativeforge.services.nm_wa_playwright_smoke_runner_service import (
    playwright_smoke_result_not_run,
)


def test_invariants() -> None:
    pkt = build_playwright_e2e_closeout_packet(
        head_before="a",
        head_after="b",
        playwright_result=playwright_smoke_result_not_run("n/a"),
        commits_created=[],
        stash_status="ok",
        uv_lock_status="ok",
        package_dependency_changes="none",
    )
    assert len(pkt["hard_invariants_covered"]) == 10
