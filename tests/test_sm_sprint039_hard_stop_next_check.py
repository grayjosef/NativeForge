"""Sprint 039: hard-stop when operator next-check missing under review."""

from __future__ import annotations

from nativeforge.services.nm_wa_operator_surfacing_demo_artifact_service import (
    build_demo_artifact,
)
from nativeforge.services.nm_wa_smoke_runner_service import (
    run_nm_wa_operator_surfacing_smoke,
)


def test_hard_stop_missing_next_check() -> None:
    a = build_demo_artifact()
    a["operator_next_check_summary"]["rows_with_next_checks"] = 0
    r = run_nm_wa_operator_surfacing_smoke(artifact=a)
    assert r["overall_status"] == "FAIL"
    assert any(
        s["surface"] == "operator_next_check_display" and s["status"] == "FAIL"
        for s in r["surfaces"]
    )
