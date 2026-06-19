"""Sprint 208: hardened profile record assembler."""

from __future__ import annotations

from nativeforge.services.org_applicant_profile_demo_fixture_service import (
    load_org_applicant_profile_fixtures,
)
from nativeforge.services.org_applicant_profile_hardened_record_service import (
    SCHEMA_VERSION,
    build_hardened_org_applicant_profile_record,
)


def test_hardened_record_assembles_evaluation() -> None:
    raw = load_org_applicant_profile_fixtures()[0]
    record = build_hardened_org_applicant_profile_record(raw)
    assert record["schema_version"] == SCHEMA_VERSION
    assert "evaluation" in record
    assert record["preview_only"] is True


def test_hardened_record_flags_no_runtime_mutation() -> None:
    raw = load_org_applicant_profile_fixtures()[0]
    record = build_hardened_org_applicant_profile_record(raw)
    assert record["no_runtime_db_mutation"] is True
