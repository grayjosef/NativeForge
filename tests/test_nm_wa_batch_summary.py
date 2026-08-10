"""Sprint 22: batch classify+match summary across NM/WA."""

from __future__ import annotations

from nativeforge.services.nm_wa_pilot_rollup_service import (
    build_batch_classify_match_summary,
)

_GRANTS = [
    {
        "grant_id": "batch-001",
        "opportunity_title": "Tribal Discretionary Grant",
        "program_area": "health",
        "recognition_requirement": "federal_required",
    }
]


def test_batch_summary_covers_nm_and_wa() -> None:
    summary = build_batch_classify_match_summary(grants=_GRANTS)
    assert summary["offline_only"] is True
    assert summary["all_needs_operator_review"] is True
    assert summary["per_state"]["NM"]["profile_count"] == 22
    assert summary["per_state"]["WA"]["profile_count"] == 29
    nm = summary["per_state"]["NM"]
    wa = summary["per_state"]["WA"]
    assert nm["match_count"] == nm["profile_count"] * nm["grant_count"]
    assert wa["match_count"] == wa["profile_count"] * wa["grant_count"]
    assert summary["total_match_count"] == nm["match_count"] + wa["match_count"]
