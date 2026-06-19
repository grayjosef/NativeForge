"""Sprint 192: discovery intake classification bridge."""

from __future__ import annotations

from nativeforge.services.native_relevance_classification_demo_fixture_service import (
    load_demo_classification_fixtures,
)
from nativeforge.services.native_relevance_classification_discovery_bridge_service import (
    SCHEMA_VERSION,
    attach_classification_preview_to_intake_summary,
)


def test_bridge_attaches_preview_block() -> None:
    summary = {"schema_version": "nf_discovery_intake_summary_v1", "candidate_count": 2}
    candidates = load_demo_classification_fixtures()[:2]
    merged = attach_classification_preview_to_intake_summary(summary, candidates)
    preview = merged["native_relevance_classification_preview"]
    assert preview["schema_version"] == SCHEMA_VERSION
    assert preview["preview_count"] == 2
    assert len(preview["previews"]) == 2
    assert preview["advisory_only"] is True
