"""Sprint 037: fail browser smoke when activation controls enabled."""

from __future__ import annotations

from nativeforge.services.nm_wa_browser_demo_bridge_service import (
    build_browser_demo_bridge_payload,
)
from nativeforge.services.nm_wa_browser_smoke_runner_service import (
    run_nm_wa_browser_demo_smoke,
)


def test_activation_controls_fail() -> None:
    p = build_browser_demo_bridge_payload()
    p["ui_flags"]["show_activation_controls"] = True
    r = run_nm_wa_browser_demo_smoke(payload=p)
    assert r["overall_status"] == "FAIL"
    assert "activation_or_submission_controls" in r["failures"]
