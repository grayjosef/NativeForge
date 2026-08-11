"""Sprint 017: provenance/evidence summary in demo artifact."""

from __future__ import annotations

from nativeforge.services.nm_wa_operator_surfacing_demo_artifact_service import (
    build_demo_artifact,
)


def test_provenance_summary() -> None:
    a = build_demo_artifact()
    p = a["provenance_evidence_summary"]
    assert p["notes_visible"] is True
    assert isinstance(p["combined_evidence_provenance_summary"], dict)
