"""Sprint 197: org/applicant profile schema."""

from __future__ import annotations

from nativeforge.services.org_applicant_profile_schema_service import (
    FIELD_LEGAL_NAME,
    FIELD_TRIBAL_GOVERNMENT_STATUS,
    PROFILE_SCHEMA_FIELDS,
    SCHEMA_VERSION,
    build_profile_schema_contract,
    is_valid_profile_field,
)


def test_profile_schema_includes_required_fields() -> None:
    assert len(PROFILE_SCHEMA_FIELDS) == 20
    for field in (
        "legal_name",
        "entity_type",
        "tribal_government_status",
        "federally_recognized_status",
        "native_serving_nonprofit_status",
        "geography",
        "past_awards",
        "contacts",
    ):
        assert field in PROFILE_SCHEMA_FIELDS


def test_build_contract() -> None:
    contract = build_profile_schema_contract()
    assert contract["schema_version"] == SCHEMA_VERSION
    assert contract["field_count"] == 20


def test_invalid_field_rejected() -> None:
    assert is_valid_profile_field(FIELD_LEGAL_NAME)
    assert not is_valid_profile_field("bogus")
    assert FIELD_TRIBAL_GOVERNMENT_STATUS in PROFILE_SCHEMA_FIELDS
