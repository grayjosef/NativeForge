"""Sprint 176: discovery intake bridge."""

from __future__ import annotations

from nativeforge.services.funding_opportunity_intake_demo_fixture_service import (
    load_demo_fixture_corpus,
)
from nativeforge.services.funding_opportunity_intake_discovery_bridge_service import (
    SCHEMA_VERSION,
    attach_hardened_preview_to_intake_summary,
)


def test_bridge_attaches_preview() -> None:
    rows = load_demo_fixture_corpus()[:1]
    out = attach_hardened_preview_to_intake_summary({"counts": {}}, rows)
    prev = out["funding_opportunity_intake_hardening_preview"]
    assert prev["schema_version"] == SCHEMA_VERSION
    assert prev["preview_count"] == 1
