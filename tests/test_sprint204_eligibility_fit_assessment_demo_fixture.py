"""Sprint 204: synthetic demo fixtures."""

from __future__ import annotations

from nativeforge.services.eligibility_fit_assessment_demo_fixture_service import (
    SCHEMA_VERSION,
    build_demo_fixture_catalog,
    load_applicant_profile_fixtures,
    load_opportunity_fixtures,
    resolve_profile_for_opportunity,
)


def test_load_fixtures() -> None:
    opportunities = load_opportunity_fixtures()
    profiles = load_applicant_profile_fixtures()
    assert len(opportunities) >= 4
    assert len(profiles) >= 4


def test_resolve_profile_for_opportunity() -> None:
    opp = next(o for o in load_opportunity_fixtures() if o["fixture_key"] == "efa_demo_strong_fit")
    profile = resolve_profile_for_opportunity(opp)
    assert profile["fixture_key"] == "efa_profile_complete_tribe"


def test_build_catalog() -> None:
    catalog = build_demo_fixture_catalog()
    assert catalog["schema_version"] == SCHEMA_VERSION
    assert catalog["synthetic_only"] is True
