"""Sprint 038: combined surfacing declares no classify/match logic change."""

from __future__ import annotations

from nativeforge.services.nm_wa_combined_operator_surfacing_service import (
    build_combined_operator_review_queue,
)

_G = [{"grant_id": "os-c-038", "opportunity_title": "Tribal Discretionary Grant", "program_area": "health", "recognition_requirement": "federal_required"}]


def test_no_match_logic_change_flag() -> None:
    q = build_combined_operator_review_queue(grants=_G)
    assert q["does_not_alter_classify_match_logic"] is True
    assert q["advisory_only"] is True
    assert q["source_activation"] is False
