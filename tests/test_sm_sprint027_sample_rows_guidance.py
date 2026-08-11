"""Sprint 027: sample rows show next-check and missing data."""

from __future__ import annotations

from nativeforge.services.nm_wa_operator_surfacing_demo_render_service import (
    build_demo_visibility_payload,
)


def test_sample_rows_guidance() -> None:
    p = build_demo_visibility_payload()
    for r in p["sample_rows"]:
        assert r.get("human_review_required") is True
        assert r.get("operator_next_check")
        assert r.get("final_eligibility_claim_allowed") is False
