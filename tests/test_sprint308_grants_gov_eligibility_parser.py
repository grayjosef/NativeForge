"""Sprint 308: Grants.gov eligibility parser."""

from __future__ import annotations

import json
from pathlib import Path

from nativeforge.services.grants_gov_eligibility_parser_service import (
    parse_grants_gov_synopsis_eligibility,
)


def test_tedc_fixture_tribal_eligible_and_eligibility_text() -> None:
    detail_path = (
        Path(__file__).resolve().parents[1]
        / "fixtures"
        / "source_ingestion"
        / "grants_gov_fetch_opportunity_362648.json"
    )
    raw = json.loads(detail_path.read_text(encoding="utf-8"))
    synopsis = (raw.get("data") or {}).get("synopsis") or {}
    result = parse_grants_gov_synopsis_eligibility(synopsis)
    assert result["tribal_eligible"] is True
    assert "Applicant types:" in result["eligibility_text"]
    assert "Indian Tribes" in result["eligibility_text"]
    assert result["applicant_types_text"]
    assert result["applicant_type_ids"] == ["07", "11"]
    type_ids = {str(x.get("id")) for x in synopsis.get("applicantTypes") or []}
    assert type_ids & {"07", "11"}


def test_tribal_type_ids_drive_eligibility() -> None:
    result = parse_grants_gov_synopsis_eligibility(
        {
            "applicantTypes": [
                {"id": "07", "description": "Native American tribal governments"},
                {"id": "11", "description": "Native American tribal organizations"},
            ],
            "applicantEligibilityDesc": "Only Indian Tribes are eligible.",
        }
    )
    assert result["tribal_eligible"] is True
    assert "Native American tribal governments" in result["eligibility_text"]
    assert "Only Indian Tribes are eligible." in result["eligibility_text"]
