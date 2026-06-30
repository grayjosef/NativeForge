"""Grants.gov eligibility completeness (Path A): forecast merge + backfill."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from nativeforge.services.grant_eligibility_conditions_service import (
    enrich_grant_with_eligibility_metadata,
)
from nativeforge.services.grants_gov_eligibility_completeness_service import (
    complete_grant_from_fetch_opportunity_detail,
    grant_needs_eligibility_completeness,
    maybe_complete_grant_eligibility,
)
from nativeforge.services.grants_gov_eligibility_parser_service import (
    parse_grants_gov_opportunity_eligibility,
    parse_grants_gov_synopsis_eligibility,
    summarize_grants_gov_attachment_inventory,
)
from nativeforge.services.recognition_requirement_derivation_service import (
    derive_recognition_requirement_bundle,
)

_TMG_FORECAST_DETAIL = {
    "opportunityNumber": "HHS-2026-IHS-TMD-0001",
    "opportunityTitle": "Tribal Management Grant (TMG) Program",
    "owningAgencyCode": "IHS",
    "docType": "forecast",
    "forecast": {
        "agencyCode": "IHS",
        "applicantEligibilityDesc": (
            "Urban Indian organization as defined by 25 U.S.C. 1603(29), "
            "that is currently administering a contract under 25 U.S.C. 1653."
        ),
        "forecastDesc": "Tribal Management Grant forecast notice.",
    },
}

_LA_REAL_035_DETAIL = {
    "opportunityNumber": "DOT-TSSP-2026",
    "opportunityTitle": "Tribal Transportation Safety Strategy Pilot Program",
    "docType": "synopsis",
    "synopsis": {
        "agencyName": "DOT",
        "applicantTypes": [
            {
                "id": "25",
                "description": (
                    'Others (see text field entitled "Additional Information on Eligibility" '
                    "for clarification)"
                ),
            }
        ],
        "applicantEligibilityDesc": (
            "Qualified institutions of higher education with Tribal communities and nonprofits."
        ),
        "synopsisDesc": "Tribal transportation safety pilot synopsis.",
    },
    "synopsisAttachmentFolders": [
        {
            "folderType": "Full Announcement",
            "synopsisAttachments": [
                {
                    "id": 999001,
                    "fileName": "Tribal Safety Pilot NOFO Final.pdf",
                    "mimeType": "application/pdf",
                    "fileLobSize": 483745,
                }
            ],
        }
    ],
}


def test_forecast_only_parse_ac1_tmg() -> None:
    parsed = parse_grants_gov_opportunity_eligibility(_TMG_FORECAST_DETAIL)
    assert parsed["eligibility_text_source"] == "forecast"
    assert "Urban Indian organization" in parsed["eligibility_text"]
    assert parsed["eligibility_provenance"]["forecast_substantive"] is True
    assert parsed["eligibility_provenance"]["synopsis_substantive"] is False


def test_forecast_derives_state_ok_with_source_forecast() -> None:
    grant = complete_grant_from_fetch_opportunity_detail(
        {
            "grant_id": "la-real-009",
            "opportunity_title": "Tribal Management Grant (TMG) Program",
            "agency": "Indian Health Service",
            "eligibility_text": "",
            "grants_gov_opportunity_id": "360298",
        },
        _TMG_FORECAST_DETAIL,
    )
    bundle = derive_recognition_requirement_bundle(grant)
    assert bundle["recognition_requirement"] == "state_ok"
    assert bundle["recognition_requirement_source"] == "forecast"
    assert grant["eligibility_text_source"] == "forecast"
    assert grant["eligibility_provenance"]["primary_source"] == "forecast"


def test_empty_on_success_backfill_ac2_la_real_035_class() -> None:
    grant = {
        "grant_id": "la-real-035",
        "opportunity_title": "Tribal Transportation Safety Strategy Pilot Program",
        "agency": "",
        "eligibility_text": "",
        "real_fetch": True,
        "grants_gov_opportunity_id": "362956",
    }
    assert grant_needs_eligibility_completeness(grant)
    completed = complete_grant_from_fetch_opportunity_detail(grant, _LA_REAL_035_DETAIL)
    assert len(str(completed.get("eligibility_text") or "")) > 50
    assert completed["eligibility_text_source"] in {"synopsis", "merged"}
    assert completed["grants_gov_attachment_inventory"]["attachment_count"] == 1
    assert completed["grants_gov_attachment_inventory"]["pdf_count"] == 1


def test_attachment_inventory_metadata_only_from_tedc_fixture() -> None:
    detail_path = (
        Path(__file__).resolve().parents[1]
        / "fixtures"
        / "source_ingestion"
        / "grants_gov_fetch_opportunity_362648.json"
    )
    raw = json.loads(detail_path.read_text(encoding="utf-8"))
    inv = summarize_grants_gov_attachment_inventory(raw.get("data") or {})
    assert inv["attachment_count"] >= 1
    assert inv["pdf_count"] >= 1
    assert inv["parsed"] is False
    assert inv["attachments"][0]["file_name"].endswith(".pdf")


def test_synopsis_parser_backward_compatible() -> None:
    result = parse_grants_gov_synopsis_eligibility(
        {
            "applicantTypes": [{"id": "07", "description": "Native American tribal governments (Federally recognized)"}],
            "applicantEligibilityDesc": "Only federally recognized tribes.",
        }
    )
    assert result["applicant_type_ids"] == ["07"]
    assert "federally recognized tribes" in result["eligibility_text"]


def test_maybe_complete_live_fetch_mock() -> None:
    grant = {
        "grant_id": "la-real-009",
        "eligibility_text": "",
        "grants_gov_opportunity_id": "360298",
        "opportunity_title": "Tribal Management Grant (TMG) Program",
        "agency": "IHS",
    }
    with patch(
        "nativeforge.services.grants_gov_eligibility_completeness_service.fetch_grants_gov_opportunity_detail",
        return_value=(_TMG_FORECAST_DETAIL, True),
    ):
        completed = maybe_complete_grant_eligibility(grant, allow_live_fetch=True)
    assert completed["eligibility_text"]
    assert completed["eligibility_text_source"] == "forecast"


def test_foreign_yseali_stays_unknown_after_completeness() -> None:
    """Honesty: foreign-org eligibility text does not invent tribal recognition tier."""
    grant = complete_grant_from_fetch_opportunity_detail(
        {
            "grant_id": "la-real-012",
            "opportunity_title": "YSEALI Workshop",
            "agency": "State",
            "eligibility_text": (
                "Applicant types: Others (see text field entitled "
                '"Additional Information on Eligibility" for clarification)\n\n'
                "For-profit entities are not eligible to apply for this NOFO."
            ),
            "eligibility_text_source": "synopsis",
        },
        {"synopsis": {"applicantEligibilityDesc": "For-profit entities are not eligible."}},
    )
    enriched = enrich_grant_with_eligibility_metadata(grant)
    assert enriched["recognition_requirement"] == "unknown"
