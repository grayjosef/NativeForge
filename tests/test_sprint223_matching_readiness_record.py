"""Sprint 223: matching + readiness record assembler."""

from __future__ import annotations

from nativeforge.services.matching_readiness_demo_fixture_service import (
    load_matching_readiness_demo_pairs,
    resolve_demo_pair,
)
from nativeforge.services.matching_readiness_record_service import (
    SCHEMA_VERSION,
    build_matching_readiness_record,
)


def test_record_assembles_stages_and_evaluations() -> None:
    pair = next(p for p in load_matching_readiness_demo_pairs() if p["fixture_key"] == "mr_demo_strong_fit")
    opp, profile = resolve_demo_pair(pair)
    record = build_matching_readiness_record(opp, profile, pair_meta=pair)
    assert record["schema_version"] == SCHEMA_VERSION
    assert "stage5_opportunity_hardening_preview" in record
    assert "stage7_org_applicant_profile" in record
    assert "match_label" in record
    assert "readiness_label" in record
    assert record["reconciliation"]["canonical_fit_evaluator"] == "eligibility_fit_assessment_evaluator_service"


def test_record_includes_next_actions() -> None:
    pair = load_matching_readiness_demo_pairs()[0]
    opp, profile = resolve_demo_pair(pair)
    record = build_matching_readiness_record(opp, profile, pair_meta=pair)
    assert isinstance(record["next_actions"], list)
