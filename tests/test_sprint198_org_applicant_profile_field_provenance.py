"""Sprint 198: field-level provenance."""

from __future__ import annotations

from nativeforge.services.org_applicant_profile_field_provenance_service import (
    CAPTURE_SYNTHETIC_FIXTURE,
    SCHEMA_VERSION,
    build_field_provenance_contract,
    build_profile_field_provenance,
)


def test_build_field_provenance() -> None:
    prov = build_profile_field_provenance(
        field_name="legal_name",
        field_value="Illustrative Northwest Tribe",
        capture_method=CAPTURE_SYNTHETIC_FIXTURE,
        fixture_key="oap_demo_tribal_government",
    )
    assert prov["schema_version"] == SCHEMA_VERSION
    assert prov["provenance_first"] is True


def test_build_contract() -> None:
    contract = build_field_provenance_contract()
    assert contract["schema_version"] == SCHEMA_VERSION
