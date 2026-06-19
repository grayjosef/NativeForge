"""Sprint 207: operator next-check builder."""

from __future__ import annotations

from nativeforge.services.eligibility_fit_assessment_demo_fixture_service import (
    load_opportunity_fixtures,
    resolve_profile_for_opportunity,
)
from nativeforge.services.eligibility_fit_assessment_operator_next_check_service import (
    SCHEMA_VERSION,
    build_operator_next_check_guidance,
)


def test_operator_next_check_for_incomplete_profile() -> None:
    opp = next(
        o for o in load_opportunity_fixtures() if o["fixture_key"] == "efa_demo_incomplete_profile"
    )
    profile = resolve_profile_for_opportunity(opp)
    guidance = build_operator_next_check_guidance(opp, profile)
    assert guidance["schema_version"] == SCHEMA_VERSION
    assert len(guidance["operator_next_checks"]) >= 1
