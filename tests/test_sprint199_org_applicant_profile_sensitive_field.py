"""Sprint 199: sensitive-field flags."""

from __future__ import annotations

from nativeforge.services.org_applicant_profile_schema_service import FIELD_CONTACTS
from nativeforge.services.org_applicant_profile_sensitive_field_service import (
    SCHEMA_VERSION,
    build_sensitive_field_flags,
    is_sensitive_profile_field,
)


def test_contacts_are_sensitive() -> None:
    assert is_sensitive_profile_field(FIELD_CONTACTS)


def test_build_sensitive_field_flags() -> None:
    result = build_sensitive_field_flags(["legal_name", "entity_type", "contacts"])
    assert result["schema_version"] == SCHEMA_VERSION
    assert result["sensitive_field_flags"]["contacts"] is True
    assert result["sensitive_field_flags"]["entity_type"] is False
