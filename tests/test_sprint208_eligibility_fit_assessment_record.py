"""Sprint 208: eligibility fit assessment record assembler."""

from __future__ import annotations

from nativeforge.services.eligibility_fit_assessment_demo_fixture_service import (
    load_opportunity_fixtures,
    resolve_profile_for_opportunity,
)
from nativeforge.services.eligibility_fit_assessment_record_service import (
    SCHEMA_VERSION,
    build_eligibility_fit_assessment_record,
)


def test_record_assembles_assessment_and_guidance() -> None:
    opp = next(o for o in load_opportunity_fixtures() if o["fixture_key"] == "efa_demo_strong_fit")
    profile = resolve_profile_for_opportunity(opp)
    record = build_eligibility_fit_assessment_record(opp, profile)
    assert record["schema_version"] == SCHEMA_VERSION
    assert "assessment" in record
    assert "operator_next_check" in record
    assert record["native_relevance_preview"] is not None


def test_record_flags_preview_only() -> None:
    opp = load_opportunity_fixtures()[0]
    profile = resolve_profile_for_opportunity(opp)
    record = build_eligibility_fit_assessment_record(opp, profile)
    assert record["preview_only"] is True
    assert record["no_live_ingestion"] is True
