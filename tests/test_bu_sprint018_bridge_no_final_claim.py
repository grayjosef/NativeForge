"""Sprint 018: bridge preserves no-final-claim behavior."""

from __future__ import annotations

from nativeforge.services.nm_wa_browser_demo_bridge_service import (
    build_browser_demo_bridge_payload,
)


def test_no_final_claim() -> None:
    p = build_browser_demo_bridge_payload()
    assert p["final_eligibility_claim_allowed"] is False
    assert all(r.get("final_eligibility_claim_allowed") is False for r in p["rows"])
