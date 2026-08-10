"""Sprint 034: combined confidence distribution reporting."""

from __future__ import annotations

from nativeforge.services.nm_wa_combined_operator_surfacing_service import (
    build_combined_operator_review_queue,
)

_G = [{"grant_id": "os-c-034", "opportunity_title": "Tribal Discretionary Grant", "program_area": "health", "recognition_requirement": "federal_required"}]


def test_confidence_distribution() -> None:
    q = build_combined_operator_review_queue(grants=_G)
    dist = q["combined_confidence_distribution"]
    assert dist.get("public_inferred_low", 0) == 51
