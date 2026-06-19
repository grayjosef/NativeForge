"""Sprint 206: provenance-first profile record builder."""

from __future__ import annotations

from nativeforge.services.org_applicant_profile_demo_fixture_service import (
    load_org_applicant_profile_fixtures,
)
from nativeforge.services.org_applicant_profile_record_builder_service import (
    SCHEMA_VERSION,
    build_provenance_first_profile_record,
)
from nativeforge.services.org_applicant_profile_unknown_value_policy_service import (
    UNKNOWN_VALUE,
)


def test_build_provenance_first_record() -> None:
    raw = next(
        f for f in load_org_applicant_profile_fixtures() if f["fixture_key"] == "oap_demo_tribal_government"
    )
    record = build_provenance_first_profile_record(raw)
    assert record["schema_version"] == SCHEMA_VERSION
    assert record["provenance_first"] is True
    assert len(record["field_provenance"]) == 20


def test_invented_field_becomes_unknown() -> None:
    raw = next(
        f for f in load_org_applicant_profile_fixtures() if f["fixture_key"] == "oap_demo_verified_attempt"
    )
    record = build_provenance_first_profile_record(raw)
    assert record["profile_fields"]["tribal_government_status"] == UNKNOWN_VALUE
