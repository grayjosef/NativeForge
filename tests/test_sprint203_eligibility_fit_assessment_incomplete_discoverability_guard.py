"""Sprint 203: incomplete discoverability guard."""

from __future__ import annotations

from nativeforge.services.eligibility_fit_assessment_incomplete_discoverability_guard_service import (
    READINESS_INCOMPLETE,
    SCHEMA_VERSION,
    apply_incomplete_discoverability_guard,
    build_incomplete_discoverability_guard_contract,
    profile_data_complete,
)


def test_incomplete_profile_stays_discoverable() -> None:
    result = apply_incomplete_discoverability_guard(
        profile={},
        proposed_discoverable=False,
        proposed_human_review_required=False,
        proposed_readiness="unknown",
    )
    assert result["final_discoverable"] is True
    assert result["final_human_review_required"] is True
    assert result["final_readiness"] == READINESS_INCOMPLETE
    assert result["over_filter_blocked"] is True


def test_complete_profile_passes_through() -> None:
    profile = {
        "organization_name": "Demo Tribe",
        "applicant_type": "tribal_government",
        "service_geography": "northwest",
    }
    result = apply_incomplete_discoverability_guard(
        profile=profile,
        proposed_discoverable=True,
        proposed_human_review_required=False,
        proposed_readiness="complete",
    )
    assert result["over_filter_blocked"] is False
    assert profile_data_complete(profile)


def test_build_contract() -> None:
    contract = build_incomplete_discoverability_guard_contract()
    assert contract["schema_version"] == SCHEMA_VERSION
