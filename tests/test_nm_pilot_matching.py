"""NM-07: NM pilot classify+match — federal gate, posture advisory, review label."""

from __future__ import annotations

import pytest

from nativeforge.services.nm_pilot_classify_match_orchestrator_service import (
    run_nm_pilot_classify_match_block,
)
from nativeforge.services.nm_pilot_fixture_loader_service import (
    EXPECTED_PROFILE_COUNT,
    fixtures_present,
)
from nativeforge.services.pilot_grant_posture_advisory_service import (
    build_grant_posture_advisory,
)

_SYNTH_GRANTS = [
    {
        "grant_id": "nm-test-fed-001",
        "opportunity_title": "Aid to Tribal Governments",
        "program_area": "governance",
        "recognition_requirement": "federal_required",
        "applicant_types": ["tribal_government"],
    },
    {
        "grant_id": "nm-test-disc-001",
        "opportunity_title": "Community Development Discretionary Grant",
        "program_area": "community_development",
        "recognition_requirement": "federal_required",
    },
]


@pytest.mark.skipif(
    not fixtures_present()["profiles"],
    reason="NM pilot fixtures not present",
)
def test_nm_federal_no_tier_mismatch_on_federal_required() -> None:
    block = run_nm_pilot_classify_match_block(
        require_fixtures=True, grants=_SYNTH_GRANTS
    )
    fed_blocks = [
        m
        for m in block["matches"]
        if m.get("recognition_requirement") == "federal_required"
        and m.get("recognition_tier_mismatch")
    ]
    assert not fed_blocks


@pytest.mark.skipif(
    not fixtures_present()["profiles"],
    reason="NM pilot fixtures not present",
)
def test_nm_grant_posture_advisory_not_hard_filter() -> None:
    block = run_nm_pilot_classify_match_block(
        require_fixtures=True, grants=_SYNTH_GRANTS
    )
    compact_profiles = [
        p for p in block["per_profile"] if p["grant_posture"] == "compact_heavy"
    ]
    assert compact_profiles
    sample = compact_profiles[0]
    assert sample["discretionary_advisory_lower_still_included"] > 0
    assert block["grant_posture_advisory_only"] is True
    lower_rows = [
        m
        for m in block["matches"]
        if m["grant_posture_advisory"]["advisory_ranking_hint"] == "lower"
    ]
    assert lower_rows
    assert all(not m["grant_posture_advisory"]["hard_filter"] for m in lower_rows)
    assert any(not m["excluded_from_match_set"] for m in lower_rows)


@pytest.mark.skipif(
    not fixtures_present()["profiles"],
    reason="NM pilot fixtures not present",
)
def test_nm_all_matches_needs_operator_review() -> None:
    block = run_nm_pilot_classify_match_block(
        require_fixtures=True, grants=_SYNTH_GRANTS
    )
    assert block["all_needs_operator_review"] is True
    assert block["profile_count"] == EXPECTED_PROFILE_COUNT
    assert len(block["matches"]) == block["grant_count"] * block["profile_count"]


def test_nm_grant_posture_advisory_contract() -> None:
    adv = build_grant_posture_advisory(
        grant_posture="compact_heavy",
        grant={"opportunity_title": "Community Development Discretionary Grant"},
    )
    assert adv["advisory_only"] is True
    assert adv["hard_filter"] is False
    assert adv["advisory_ranking_hint"] == "lower"
