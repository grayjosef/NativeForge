"""Sprint 220: synthetic demo pairs."""

from __future__ import annotations

from nativeforge.services.matching_readiness_demo_fixture_service import (
    SCHEMA_VERSION,
    build_demo_pair_catalog,
    load_matching_readiness_demo_pairs,
    resolve_demo_pair,
)


def test_load_demo_pairs() -> None:
    pairs = load_matching_readiness_demo_pairs()
    assert len(pairs) >= 5


def test_resolve_demo_pair() -> None:
    pair = next(p for p in load_matching_readiness_demo_pairs() if p["fixture_key"] == "mr_demo_strong_fit")
    opportunity, profile = resolve_demo_pair(pair)
    assert opportunity.get("fixture_key") == "efa_demo_strong_fit"
    assert profile.get("fixture_key") == "efa_profile_complete_tribe"


def test_build_catalog() -> None:
    catalog = build_demo_pair_catalog()
    assert catalog["schema_version"] == SCHEMA_VERSION
    assert catalog["synthetic_only"] is True
