"""Sprint 242: canonical operator guidance reconciliation."""

from __future__ import annotations

from nativeforge.services.canonical_operator_guidance_reconciliation_service import (
    build_reconciliation_contract,
    map_fit_topic_to_canonical,
    reconcile_operator_next_checks,
)
from nativeforge.services.eligibility_fit_assessment_operator_next_check_service import (
    build_operator_next_check_guidance,
)
from nativeforge.services.eligibility_fit_assessment_demo_fixture_service import (
    load_applicant_profile_fixtures,
    load_opportunity_fixtures,
)


def test_fit_topic_maps_to_canonical() -> None:
    assert map_fit_topic_to_canonical("human_gate") == "needs_operator_review"
    assert map_fit_topic_to_canonical("missing_profile") == "needs_more_profile_data"


def test_reconcile_operator_next_checks_from_fixture() -> None:
    opp = next(
        o for o in load_opportunity_fixtures() if o["fixture_key"] == "efa_demo_incomplete_profile"
    )
    profile = next(
        p for p in load_applicant_profile_fixtures() if p["fixture_key"] == "efa_profile_incomplete"
    )
    guidance = build_operator_next_check_guidance(opp, profile)
    canonical = reconcile_operator_next_checks(guidance)
    topics = {c["topic"] for c in canonical}
    assert "needs_more_profile_data" in topics
    assert all(c.get("guidance") for c in canonical)


def test_reconciliation_contract_complete() -> None:
    contract = build_reconciliation_contract()
    assert contract["reconciliation_status"] == "complete"
    assert "human_gate" in contract["topic_map"]
