"""Sprint 035: hard-stop on missing combined review queue."""

from __future__ import annotations

from nativeforge.services.nm_wa_operator_surfacing_demo_artifact_service import (
    build_demo_artifact,
)
from nativeforge.services.nm_wa_smoke_runner_service import (
    run_nm_wa_operator_surfacing_smoke,
)


def test_hard_stop_missing_combined() -> None:
    a = build_demo_artifact()
    a["combined_review_queue"] = {"rows": [], "combined_profile_count": 0}
    r = run_nm_wa_operator_surfacing_smoke(artifact=a)
    assert r["overall_status"] == "FAIL"
    assert any(s["surface"] == "combined_review_queue_report" and s["status"] == "FAIL" for s in r["surfaces"])
