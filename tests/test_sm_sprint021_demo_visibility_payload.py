"""Sprint 021: demo visibility payload."""

from __future__ import annotations

from nativeforge.services.nm_wa_operator_surfacing_demo_render_service import (
    build_demo_visibility_payload,
)


def test_demo_visibility_payload() -> None:
    p = build_demo_visibility_payload()
    assert p["demo_dev_only"] is True
    assert p["offline_only"] is True
    assert p["combined_profile_count"] == 51
    assert p["final_eligibility_claim_allowed"] is False
    assert len(p["sample_rows"]) == 5
