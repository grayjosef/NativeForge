"""Sprint 201: unknown value policy."""

from __future__ import annotations

from nativeforge.services.org_applicant_profile_unknown_value_policy_service import (
    SCHEMA_VERSION,
    UNKNOWN_VALUE,
    build_unknown_value_policy_contract,
    is_unknown_value,
    normalize_unknown_field_value,
)


def test_none_is_unknown() -> None:
    assert is_unknown_value(None)
    assert normalize_unknown_field_value(None) == UNKNOWN_VALUE


def test_blank_string_is_unknown() -> None:
    assert is_unknown_value("")
    assert normalize_unknown_field_value("  ") == UNKNOWN_VALUE


def test_known_value_preserved() -> None:
    assert normalize_unknown_field_value("Illustrative Tribe") == "Illustrative Tribe"


def test_build_contract() -> None:
    contract = build_unknown_value_policy_contract()
    assert contract["schema_version"] == SCHEMA_VERSION
    assert contract["never_invent_data"] is True
