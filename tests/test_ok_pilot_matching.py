"""OK pilot: federal tribe matching + grant_posture advisory + program-fit."""

from __future__ import annotations

from pathlib import Path

import pytest

from nativeforge.services.eligibility_fit_assessment_dimension_vocabulary_service import (  # noqa: E501
    FIT_STATUS_UNKNOWN,
)
from nativeforge.services.matching_profile_provenance_service import (
    CAPTURE_PUBLIC_INFERRED,
)
from nativeforge.services.ok_pilot_classify_match_orchestrator_service import (
    run_ok_pilot_classify_match_block,
)
from nativeforge.services.ok_pilot_fixture_loader_service import (
    EXPECTED_PROFILE_COUNT,
    fixtures_present,
    load_ok_tribal_profiles,
    require_ok_pilot_fixtures,
)
from nativeforge.services.ok_pilot_honesty_regression_service import (
    run_ok_pilot_honesty_regression,
)
from nativeforge.services.ok_pilot_profile_loader_service import (
    list_ok_pilot_profiles,
    resolve_ok_pilot_profile,
)
from nativeforge.services.pilot_grant_posture_advisory_service import (
    build_grant_posture_advisory,
)
from nativeforge.services.pilot_program_areas_normalization_service import (
    normalize_program_areas,
)

_FIXTURES_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "ok_pilot"


def test_normalize_program_areas_object_form() -> None:
    raw = [
        {
            "area": "Healthcare (IHS compact)",
            "confidence": "high",
            "provenance": "public_fact",
            "source": "https://example.com",
        }
    ]
    norm = normalize_program_areas(raw)
    assert norm["program_areas"] == ["Healthcare (IHS compact)"]
    assert norm["program_areas_unknown"] is False
    assert len(norm["program_areas_detail"] or []) == 1


def test_normalize_program_areas_legacy_strings() -> None:
    norm = normalize_program_areas(["housing", "education"])
    assert norm["program_areas"] == ["housing", "education"]
    assert norm["program_areas_unknown"] is False


def test_normalize_program_areas_unknown() -> None:
    norm = normalize_program_areas("UNKNOWN")
    assert norm["program_areas"] == []
    assert norm["program_areas_unknown"] is True


@pytest.mark.skipif(
    not fixtures_present()["profiles"],
    reason="OK pilot fixtures not present",
)
def test_ok_fixture_loads_38_federal_profiles() -> None:
    require_ok_pilot_fixtures()
    profiles = load_ok_tribal_profiles()
    assert len(profiles) == EXPECTED_PROFILE_COUNT
    assert all(p["recognition_type"] == "federal" for p in profiles)


@pytest.mark.skipif(
    not fixtures_present()["profiles"],
    reason="OK pilot fixtures not present",
)
def test_ok_profiles_public_inferred_no_evidence_codes() -> None:
    profiles = list_ok_pilot_profiles(require_files=True)
    assert len(profiles) == EXPECTED_PROFILE_COUNT
    for p in profiles:
        prof = resolve_ok_pilot_profile(p["fixture_key"])
        assert prof["capture_method"] == CAPTURE_PUBLIC_INFERRED
        assert prof["profile_evidence_codes"] == []
        assert prof["recognition_type"] == "federal"


@pytest.mark.skipif(
    not fixtures_present()["profiles"],
    reason="OK pilot fixtures not present",
)
def test_ok_federal_no_tier_mismatch_on_federal_required() -> None:
    block = run_ok_pilot_classify_match_block(require_fixtures=True)
    fed_blocks = [
        m
        for m in block["matches"]
        if m.get("recognition_requirement") == "federal_required"
        and m.get("recognition_tier_mismatch")
    ]
    assert not fed_blocks, (
        "OK federal tribes must not tier-block federal_required grants"
    )


@pytest.mark.skipif(
    not fixtures_present()["profiles"],
    reason="OK pilot fixtures not present",
)
def test_grant_posture_advisory_not_hard_filter() -> None:
    block = run_ok_pilot_classify_match_block(require_fixtures=True)
    compact_profiles = [
        p for p in block["per_profile"] if p["grant_posture"] == "compact_heavy"
    ]
    assert compact_profiles, "expected compact_heavy OK profiles"
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
    reason="OK pilot fixtures not present",
)
def test_program_fit_unknown_profile_stays_unknown() -> None:
    block = run_ok_pilot_classify_match_block(require_fixtures=True)
    unknown_profile = next(
        p for p in block["per_profile"] if p["program_areas_unknown"] is True
    )
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


@pytest.mark.skipif(
    not fixtures_present()["profiles"],
    reason="OK pilot fixtures not present",
)
def test_all_matches_needs_operator_review() -> None:
    block = run_ok_pilot_classify_match_block(require_fixtures=True)
    assert block["all_needs_operator_review"] is True
    assert block["profile_count"] == EXPECTED_PROFILE_COUNT
    assert len(block["matches"]) == block["grant_count"] * block["profile_count"]


def test_grant_posture_advisory_contract() -> None:
    adv = build_grant_posture_advisory(
        grant_posture="compact_heavy",
        grant={"opportunity_title": "Community Development Discretionary Grant"},
    )
    assert adv["advisory_only"] is True
    assert adv["hard_filter"] is False
    assert adv["advisory_ranking_hint"] == "lower"


@pytest.mark.skipif(
    not fixtures_present()["profiles"],
    reason="OK pilot fixtures not present",
)
def test_ok_honesty_regression() -> None:
    result = run_ok_pilot_honesty_regression()
    assert result["verification_passed"]
