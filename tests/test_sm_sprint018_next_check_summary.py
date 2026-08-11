"""Sprint 018: operator next-check summary in demo artifact."""

from __future__ import annotations

from nativeforge.services.nm_wa_operator_surfacing_demo_artifact_service import (
    build_demo_artifact,
)


def test_next_check_summary() -> None:
    a = build_demo_artifact()
    n = a["operator_next_check_summary"]
    assert n["human_review_required_count"] == 51
    assert n["rows_with_next_checks"] == 51
