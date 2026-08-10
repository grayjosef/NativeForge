"""Sprint 004: readiness to classification mapping."""

from __future__ import annotations

from nativeforge.services.nm_wa_operator_surfacing_row_mapper_service import (
    map_readiness_to_classification,
)
from nativeforge.services.nm_wa_pilot_rollup_service import (
    READINESS_INCOMPLETE_PROFILE,
    READINESS_NEEDS_OPERATOR_REVIEW,
)


def test_map_incomplete_and_review_labels() -> None:
    assert (
        map_readiness_to_classification(READINESS_INCOMPLETE_PROFILE)
        == "incomplete_profile_data"
    )
    assert (
        map_readiness_to_classification(READINESS_NEEDS_OPERATOR_REVIEW)
        == "needs_operator_review"
    )
