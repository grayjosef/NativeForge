"""Sprint 033: stable ordering for combined operator review queue."""

from __future__ import annotations

from nativeforge.services.nm_wa_combined_operator_surfacing_service import (
    build_combined_operator_review_queue,
)

_G = [
    {
        "grant_id": "os-c-033",
        "opportunity_title": "Tribal Discretionary Grant",
        "program_area": "health",
        "recognition_requirement": "federal_required",
    }
]


def test_stable_ordering_deterministic() -> None:
    a = build_combined_operator_review_queue(grants=_G)["rows"]
    b = build_combined_operator_review_queue(grants=_G)["rows"]
    assert [r["profile_id"] for r in a] == [r["profile_id"] for r in b]
    # incomplete readiness precedes needs_operator_review when present
    readiness = [r["match_readiness_label"] for r in a]
    if "incomplete_profile_data" in readiness and "needs_operator_review" in readiness:
        assert readiness.index("incomplete_profile_data") < readiness.index(
            "needs_operator_review"
        )
