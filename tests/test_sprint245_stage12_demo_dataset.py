"""Sprint 244-245: Stage 12 isolated demo dataset."""

from __future__ import annotations

import json

from nativeforge.services.stage12_demo_dataset_service import (
    STAGE12_NAMESPACE,
    load_stage12_dataset_bundle,
    load_stage12_opportunities,
    load_stage12_sources,
)


def test_namespace_constant() -> None:
    assert STAGE12_NAMESPACE == "nf_stage12"


def test_sources_are_namespaced_and_fictional() -> None:
    sources = load_stage12_sources()
    assert len(sources) == 2
    for s in sources:
        assert s["fixture_key"].startswith("nf_stage12_")
        assert s["fictional_only"] is True


def test_opportunities_cover_four_archetypes() -> None:
    opps = load_stage12_opportunities()
    assert len(opps) == 4
    archetypes = {o["demo_archetype"] for o in opps}
    assert "native_specific_tribal_government" in archetypes
    assert "stale_expired" in archetypes
    stale = next(o for o in opps if o["demo_archetype"] == "stale_expired")
    assert stale["stale"] is True


def test_dataset_bundle_json_serializable() -> None:
    bundle = load_stage12_dataset_bundle()
    json.dumps(bundle)
    assert bundle["isolated"] is True
