"""Sprint 017: bridge preserves provenance and confidence labels."""

from __future__ import annotations

from nativeforge.services.nm_wa_browser_demo_bridge_service import (
    build_browser_demo_bridge_payload,
)


def test_provenance_and_confidence() -> None:
    p = build_browser_demo_bridge_payload()
    assert p["provenance_evidence_summary"]["notes_visible"] is True
    assert p["combined_summary"]["confidence_distribution"]
    assert all(r.get("confidence") for r in p["rows"])
    assert all(r.get("match_readiness_label") for r in p["rows"])
