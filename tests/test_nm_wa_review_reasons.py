"""Sprint 32: review reason derivation."""

from __future__ import annotations

from nativeforge.services.nm_wa_operator_review_service import (
    REVIEW_REASON_NO_FINAL_ELIGIBILITY_WITHOUT_EVIDENCE,
    REVIEW_REASON_PUBLIC_INFERRED_PROFILE,
    REVIEW_REASON_UNKNOWN_GRANT_POSTURE,
    REVIEW_REASON_UNKNOWN_PROGRAM_AREAS,
    derive_review_reasons,
)


def test_review_reasons_include_unknowns() -> None:
    reasons = derive_review_reasons(
        {"program_areas_unknown": True, "grant_posture": "UNKNOWN"}
    )
    assert REVIEW_REASON_PUBLIC_INFERRED_PROFILE in reasons
    assert REVIEW_REASON_NO_FINAL_ELIGIBILITY_WITHOUT_EVIDENCE in reasons
    assert REVIEW_REASON_UNKNOWN_PROGRAM_AREAS in reasons
    assert REVIEW_REASON_UNKNOWN_GRANT_POSTURE in reasons
