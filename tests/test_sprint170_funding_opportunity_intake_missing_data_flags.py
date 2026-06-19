"""Sprint 170: missing-data flags."""

from __future__ import annotations

from nativeforge.services.funding_opportunity_intake_missing_data_flags_service import (
    FLAG_MISSING_DEADLINE,
    evaluate_missing_data_flags,
)
from nativeforge.services.funding_opportunity_intake_opportunity_record_service import (
    build_provenance_first_opportunity_record,
)


def test_missing_deadline_flagged() -> None:
    rec = build_provenance_first_opportunity_record(
        {"opportunity_title": "X", "publisher_name": "A", "agency": "A"},
        fixture_key="incomplete",
    )
    out = evaluate_missing_data_flags(rec)
    assert FLAG_MISSING_DEADLINE in out["missing_data_flags"]
