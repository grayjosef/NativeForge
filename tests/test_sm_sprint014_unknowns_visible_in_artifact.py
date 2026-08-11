"""Sprint 014: unknowns remain visible in demo artifact."""

from __future__ import annotations

from nativeforge.services.nm_wa_operator_surfacing_demo_artifact_service import (
    build_demo_artifact,
)


def test_unknowns_and_review_required_preserved() -> None:
    a = build_demo_artifact()
    rows = a["combined_review_queue"]["rows"]
    assert any(r.get("missing_data") for r in rows)
    assert all(r.get("human_review_required") for r in rows)
    assert all(r.get("discoverability") == "visible_in_operator_review" for r in rows)
    assert a["operator_next_check_summary"]["rows_with_next_checks"] == len(rows)
