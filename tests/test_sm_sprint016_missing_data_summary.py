"""Sprint 016: missing-data summary present and not hidden."""

from __future__ import annotations

from nativeforge.services.nm_wa_operator_surfacing_demo_artifact_service import (
    build_demo_artifact,
)


def test_missing_data_summary() -> None:
    a = build_demo_artifact()
    s = a["missing_data_summary"]
    assert s["hidden_missing_data"] is False
    assert s["combined_missing_data_count"] >= 0
    assert isinstance(s["nm_missing_evidence_categories"], dict)
    assert isinstance(s["wa_missing_evidence_categories"], dict)
