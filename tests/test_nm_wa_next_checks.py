"""Sprint 33: next-check guidance from review reasons."""

from __future__ import annotations

from nativeforge.services.nm_wa_operator_review_service import (
    NEXT_CHECK_CONFIRM_GRANT_POSTURE,
    NEXT_CHECK_CONFIRM_PROGRAM_AREAS,
    NEXT_CHECK_HUMAN_REVIEW_MATCHES,
    REVIEW_REASON_UNKNOWN_GRANT_POSTURE,
    REVIEW_REASON_UNKNOWN_PROGRAM_AREAS,
    derive_next_check_guidance,
)


def test_next_check_guidance_maps_reasons() -> None:
    guidance = derive_next_check_guidance(
        [
            REVIEW_REASON_UNKNOWN_PROGRAM_AREAS,
            REVIEW_REASON_UNKNOWN_GRANT_POSTURE,
        ]
    )
    assert NEXT_CHECK_HUMAN_REVIEW_MATCHES in guidance
    assert NEXT_CHECK_CONFIRM_PROGRAM_AREAS in guidance
    assert NEXT_CHECK_CONFIRM_GRANT_POSTURE in guidance
