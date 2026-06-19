"""Sprint 202: no-invention guard."""

from __future__ import annotations

from nativeforge.services.org_applicant_profile_no_invention_guard_service import (
    SCHEMA_VERSION,
    apply_no_invention_guard,
    build_no_invention_guard_contract,
)
from nativeforge.services.org_applicant_profile_unknown_value_policy_service import (
    UNKNOWN_VALUE,
)


def test_invented_tribal_status_blocked() -> None:
    result = apply_no_invention_guard(
        field_name="tribal_government_status",
        raw_value="assumed_true",
        capture_method="unknown",
    )
    assert result["invention_blocked"] is True
    assert result["final_value"] == UNKNOWN_VALUE


def test_unknown_stays_unknown_for_protected_field() -> None:
    result = apply_no_invention_guard(
        field_name="federally_recognized_status",
        raw_value=None,
        capture_method="unknown",
    )
    assert result["final_value"] == UNKNOWN_VALUE


def test_documented_value_allowed_with_fixture_capture() -> None:
    result = apply_no_invention_guard(
        field_name="tribal_government_status",
        raw_value="confirmed_tribal_government",
        capture_method="synthetic_fixture",
    )
    assert result["final_value"] == "confirmed_tribal_government"
    assert result["invention_blocked"] is False


def test_build_contract() -> None:
    contract = build_no_invention_guard_contract()
    assert contract["schema_version"] == SCHEMA_VERSION
