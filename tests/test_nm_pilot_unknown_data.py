"""NM-08: unknown program areas stay discoverable and force operator review."""

from __future__ import annotations

import pytest

from nativeforge.services.eligibility_fit_assessment_dimension_vocabulary_service import (  # noqa: E501
    FIT_STATUS_UNKNOWN,
)
from nativeforge.services.matching_readiness_match_label_vocabulary_service import (
    LABEL_NEEDS_OPERATOR_REVIEW,
)
from nativeforge.services.nm_pilot_classify_match_orchestrator_service import (
    run_nm_pilot_classify_match_block,
)
from nativeforge.services.nm_pilot_fixture_loader_service import fixtures_present

_SYNTH_GRANTS = [
    {
        "grant_id": "nm-unk-001",
        "opportunity_title": "Education Support Program",
        "program_area": "education",
        "recognition_requirement": "federal_required",
    }
]


@pytest.mark.skipif(
    not fixtures_present()["profiles"],
    reason="NM pilot fixtures not present",
)
def test_nm_program_fit_unknown_profile_stays_unknown() -> None:
    block = run_nm_pilot_classify_match_block(
        require_fixtures=True, grants=_SYNTH_GRANTS
    )
    unknown_profiles = [
        p for p in block["per_profile"] if p["program_areas_unknown"] is True
    ]
    if not unknown_profiles:
        pytest.skip("no NM profile with unknown program_areas in fixtures")
    unknown_profile = unknown_profiles[0]
    rows = [
        m
        for m in block["matches"]
        if m["profile_fixture_key"] == unknown_profile["profile_fixture_key"]
        and m["opportunity_metadata"].get("program_area")
    ]
    assert rows
    assert all(
        (m.get("program_fit") or {}).get("fit_status") == FIT_STATUS_UNKNOWN
        for m in rows
    )
    assert all(m["match_label"] == LABEL_NEEDS_OPERATOR_REVIEW for m in rows)


@pytest.mark.skipif(
    not fixtures_present()["profiles"],
    reason="NM pilot fixtures not present",
)
def test_nm_unknown_profiles_remain_in_match_set() -> None:
    block = run_nm_pilot_classify_match_block(
        require_fixtures=True, grants=_SYNTH_GRANTS
    )
    assert block["matches"], "matches must remain discoverable"
    assert block["all_needs_operator_review"] is True
