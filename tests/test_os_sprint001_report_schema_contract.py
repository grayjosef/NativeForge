"""Sprint 001: operator report schema contract."""

from __future__ import annotations

from nativeforge.services.nm_wa_operator_surfacing_report_schema_service import (
    OPERATOR_REPORT_REQUIRED_FIELDS,
    build_operator_report_schema_contract,
)


def test_operator_report_schema_contract() -> None:
    c = build_operator_report_schema_contract()
    assert c["offline_only"] is True
    assert c["live_ingestion"] is False
    assert c["source_activation"] is False
    assert c["does_not_alter_classify_match_logic"] is True
    assert c["final_eligibility_claim_allowed_default"] is False
    for field in OPERATOR_REPORT_REQUIRED_FIELDS:
        assert field in c["required_fields"]
