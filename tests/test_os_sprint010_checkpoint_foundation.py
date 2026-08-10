"""Sprint 010: foundation checkpoint — schema + mapper invariants."""

from __future__ import annotations

from nativeforge.services.nm_wa_operator_surfacing_report_schema_service import (
    build_operator_report_schema_contract,
)
from nativeforge.services.nm_wa_operator_surfacing_row_mapper_service import (
    build_operator_report_rows,
)


def test_foundation_checkpoint() -> None:
    c = build_operator_report_schema_contract()
    assert c["does_not_alter_classify_match_logic"] is True
    rows = build_operator_report_rows(
        [
            {
                "state": "NM",
                "profile_fixture_key": "nm_pilot_chk",
                "readiness_label": "needs_operator_review",
            }
        ]
    )
    assert rows[0]["human_review_required"] is True
    assert rows[0]["final_eligibility_claim_allowed"] is False
