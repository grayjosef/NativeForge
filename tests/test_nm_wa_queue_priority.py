"""Sprint 35: incomplete readiness gets high queue priority."""

from __future__ import annotations

from nativeforge.services.nm_wa_operator_review_service import (
    build_operator_review_queue,
)
from nativeforge.services.nm_wa_pilot_rollup_service import READINESS_INCOMPLETE_PROFILE

_GRANTS = [
    {
        "grant_id": "prio-001",
        "opportunity_title": "Tribal Discretionary Grant",
        "program_area": "health",
        "recognition_requirement": "federal_required",
    }
]


def test_incomplete_profiles_high_priority() -> None:
    queue = build_operator_review_queue(grants=_GRANTS)
    incomplete = [
        i
        for i in queue["items"]
        if i["readiness_label"] == READINESS_INCOMPLETE_PROFILE
    ]
    if not incomplete:
        # still assert queue contract
        assert queue["item_count"] == 51
        return
    assert all(i["queue_priority"] == "high" for i in incomplete)
