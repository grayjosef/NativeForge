"""Sprint 169: provenance-first opportunity record."""

from __future__ import annotations

from nativeforge.services.funding_opportunity_intake_opportunity_record_service import (
    SCHEMA_VERSION,
    build_provenance_first_opportunity_record,
)


def test_provenance_first_record() -> None:
    rec = build_provenance_first_opportunity_record(
        {
            "opportunity_title": "Tribal language preservation",
            "opportunity_number": "FOI-001",
            "publisher_name": "Demo Agency",
            "agency": "Demo Agency",
            "application_deadline": "2026-12-31T00:00:00Z",
            "source_registry_id": "00000000-0000-0000-0000-000000000001",
            "opportunity_source_type": "federal",
        },
        fixture_key="foi_demo_complete",
    )
    assert rec["schema_version"] == SCHEMA_VERSION
    assert rec["provenance_first"] is True
    assert len(rec["field_provenance"]) >= 7
