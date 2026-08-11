"""Sprint 036: fail browser smoke on final eligibility claim."""

from __future__ import annotations

from nativeforge.services.nm_wa_browser_demo_bridge_service import (
    build_browser_demo_bridge_payload,
)
from nativeforge.services.nm_wa_browser_smoke_runner_service import (
    run_nm_wa_browser_demo_smoke,
)


def test_final_claim_fails() -> None:
    p = build_browser_demo_bridge_payload()
    p["final_eligibility_claim_allowed"] = True
    r = run_nm_wa_browser_demo_smoke(payload=p)
    assert r["overall_status"] == "FAIL"
