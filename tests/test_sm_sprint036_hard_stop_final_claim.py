"""Sprint 036: hard-stop on final eligibility claim without evidence."""

from __future__ import annotations

from nativeforge.services.nm_wa_operator_surfacing_demo_artifact_service import (
    build_demo_artifact,
)
from nativeforge.services.nm_wa_smoke_runner_service import (
    run_nm_wa_operator_surfacing_smoke,
)


def test_hard_stop_final_claim() -> None:
    a = build_demo_artifact()
    a["final_eligibility_claim_allowed"] = True
    r = run_nm_wa_operator_surfacing_smoke(artifact=a)
    assert r["overall_status"] == "FAIL"
    assert any(
        s["surface"] == "no_final_eligibility_claim_behavior" and s["status"] == "FAIL"
        for s in r["surfaces"]
    )
