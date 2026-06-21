"""Sprint 304: Grants.gov search2 API adapter."""

from __future__ import annotations

import json
from pathlib import Path

from nativeforge.services.grants_gov_search_api_adapter_service import (
    build_grants_gov_search_body,
    extract_assistance_listing_number,
    fetch_fed001_grants_gov_opportunities,
    load_recorded_grants_gov_search_fixture,
    search_grants_gov_opportunities,
)
from nativeforge.services.real_tier1_live_fetch_service import load_fed001_candidate


def _mock_post(url: str, body: dict[str, object]) -> dict[str, object]:
    fixture = (
        Path(__file__).resolve().parents[1]
        / "fixtures"
        / "source_ingestion"
        / "grants_gov_search2_bia_tedc_hit.json"
    )
    if "search2" in url:
        return json.loads(fixture.read_text(encoding="utf-8"))
    if "fetchOpportunity" in url:
        detail = (
            Path(__file__).resolve().parents[1]
            / "fixtures"
            / "source_ingestion"
            / "grants_gov_fetch_opportunity_362648.json"
        )
        return json.loads(detail.read_text(encoding="utf-8"))
    return {"errorcode": 1, "msg": "unknown", "data": {}}


def test_extract_aln_from_fed001_name() -> None:
    source = load_fed001_candidate()
    aln = extract_assistance_listing_number(str(source["source_name"]))
    assert aln == "15.020"


def test_search_body_includes_bia_agency() -> None:
    source = load_fed001_candidate()
    body = build_grants_gov_search_body(source)
    assert body["agencies"] == "DOI-BIA"
    assert body["cfda"] == "15.020"


def test_recorded_fixture_not_illustrative() -> None:
    rows = load_recorded_grants_gov_search_fixture()
    assert len(rows) == 1
    assert rows[0]["opportunity_number"] == "BIA-TEDC-2026"
    assert "Illustrative" not in rows[0]["opportunity_title"]
    assert rows[0]["fixture"] is True
    assert rows[0]["real_fetch"] is False
    assert rows[0]["fetch_mode"] == "fixture"
    assert rows[0]["tribal_eligible"] is True
    assert "Indian Tribes" in rows[0]["eligibility_text"]


def test_fed001_live_mock_returns_empty_for_tedc_only_hits() -> None:
    source = load_fed001_candidate()
    rows = fetch_fed001_grants_gov_opportunities(source, http_post=_mock_post)
    assert rows == []


def test_fetch_empty_when_aln_filter_excludes_hits() -> None:
    source = load_fed001_candidate()

    def _no_match_post(url: str, body: dict[str, object]) -> dict[str, object]:
        raw = _mock_post(url, body)
        if "search2" in url:
            raw = dict(raw)
            raw["data"] = dict(raw["data"])
            raw["data"]["oppHits"] = [
                {
                    "id": "1",
                    "number": "OTHER-001",
                    "title": "Other Program",
                    "agencyCode": "HHS",
                    "agency": "HHS",
                    "cfdaList": ["93.001"],
                }
            ]
        return raw

    rows = fetch_fed001_grants_gov_opportunities(source, http_post=_no_match_post)
    assert rows == []


def test_search_returns_hits_for_bia_keyword() -> None:
    source = {
        "source_name": "Bureau of Indian Affairs TEDC",
        "source_url": "https://www.bia.gov/topic/grants",
    }
    search = search_grants_gov_opportunities(source, http_post=_mock_post)
    assert search["hit_count"] >= 1
