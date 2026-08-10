"""Sprint 036: combined queue reuses review reason vocabulary via blockers."""

from __future__ import annotations

from nativeforge.services.nm_wa_combined_operator_surfacing_service import (
    build_combined_operator_review_queue,
)
from nativeforge.services.nm_wa_operator_review_service import (
    REVIEW_REASON_NO_FINAL_ELIGIBILITY_WITHOUT_EVIDENCE,
)

_G = [{"grant_id": "os-c-036", "opportunity_title": "Tribal Discretionary Grant", "program_area": "health", "recognition_requirement": "federal_required"}]


def test_blockers_include_shared_vocab() -> None:
    q = build_combined_operator_review_queue(grants=_G)
    assert any(
        REVIEW_REASON_NO_FINAL_ELIGIBILITY_WITHOUT_EVIDENCE in r["blockers"]
        for r in q["rows"]
    )
