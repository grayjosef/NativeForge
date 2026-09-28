"""Customer live federal search uses injected transport and never synthesizes."""

from __future__ import annotations

from nativeforge.services.customer_live_federal_search_service import (
    search_live_federal_opportunities,
)
from nativeforge.services.grants_gov_search_api_adapter_service import (
    ELIGIBILITY_TRIBAL_GOVERNMENT,
    EXPECTED_ELIGIBILITY_FACET_LABELS,
)


def _facet_payload(code: str, hits: list[dict]) -> dict:
    labels = [
        {"value": key, "label": value}
        for key, value in EXPECTED_ELIGIBILITY_FACET_LABELS.items()
    ]
    return {
        "errorcode": 0,
        "data": {
            "hitCount": len(hits),
            "oppHits": hits,
            "eligibilities": labels,
        },
    }


def test_injected_transport_returns_honest_live_rows() -> None:
    def http_post(url: str, body: dict) -> dict:
        code = str(body.get("eligibilities") or body.get("eligibility") or "")
        if ELIGIBILITY_TRIBAL_GOVERNMENT in str(body):
            return _facet_payload(
                ELIGIBILITY_TRIBAL_GOVERNMENT,
                [
                    {
                        "id": "ogg-1",
                        "number": "HHS-2026-001",
                        "title": "Tribal public health capacity",
                        "agency": "HHS",
                        "closeDate": "2026-12-01",
                    }
                ],
            )
        return _facet_payload(code or "xx", [])

    result = search_live_federal_opportunities(http_post=http_post)
    assert result["never_synthesized"] is True
    assert result["collectors_live"] == 0
    assert result["search_live"] is True
    assert result["result_count"] == 1
    row = result["results"][0]
    assert row["title"] == "Tribal public health capacity"
    assert row["native_relevance_decided"] is False
    assert row["source"] == "grants.gov"
    assert "publisher" in row["why_it_matches"].lower()


def test_broad_posted_hit_is_kept_when_it_is_not_a_tribal_class() -> None:
    def http_post(url: str, body: dict) -> dict:
        if body.get("eligibilities"):
            return _facet_payload(str(body["eligibilities"]), [])
        return _facet_payload(
            "broad",
            [
                {
                    "id": "broad-1",
                    "number": "DOC-2026-014",
                    "title": "Statewide infrastructure planning",
                    "agency": "DOC",
                    "closeDate": "2026-11-02",
                    "oppStatus": "posted",
                }
            ],
        )

    result = search_live_federal_opportunities(
        http_post=http_post, enrich_details=False
    )
    assert result["lanes"]["broad_posted_or_forecasted"] == 1
    assert result["lanes"]["publisher_applicant_class"] == 0
    row = result["results"][0]
    assert row["opportunity_number"] == "DOC-2026-014"
    assert row["native_relevance_decided"] is False
    assert row["award_ceiling"] is None
    assert "not decided" in row["why_it_matches"].lower()
    assert "eligibilities" not in (result["broad_outcome"] or {})


def test_a_publisher_class_hit_is_not_duplicated_by_the_broad_index() -> None:
    hit = {
        "id": "same-1",
        "number": "HHS-2026-001",
        "title": "Tribal public health capacity",
        "agency": "HHS",
    }

    def http_post(url: str, body: dict) -> dict:
        if body.get("eligibilities") == ELIGIBILITY_TRIBAL_GOVERNMENT:
            return _facet_payload(ELIGIBILITY_TRIBAL_GOVERNMENT, [hit])
        if body.get("eligibilities"):
            return _facet_payload(str(body["eligibilities"]), [])
        return _facet_payload("broad", [hit])

    result = search_live_federal_opportunities(
        http_post=http_post, enrich_details=False
    )
    assert result["result_count"] == 1
    assert result["results"][0]["coverage_lane"] == "publisher_applicant_class"


def test_a_detail_miss_does_not_drop_the_search_hit() -> None:
    def http_post(url: str, body: dict) -> dict:
        if "fetchOpportunity" in url:
            raise TimeoutError("detail transport failed")
        if ELIGIBILITY_TRIBAL_GOVERNMENT in str(body.get("eligibilities") or ""):
            return _facet_payload(
                ELIGIBILITY_TRIBAL_GOVERNMENT,
                [{"id": "ogg-1", "number": "HHS-2026-001", "title": "Kept"}],
            )
        return _facet_payload("x", [])

    result = search_live_federal_opportunities(http_post=http_post)
    assert result["result_count"] == 1
    assert result["results"][0]["detail_status"] == "unavailable"
    assert result["results"][0]["eligibility_text"] is None


def test_unrelated_org_is_not_in_payload() -> None:
    result = search_live_federal_opportunities(
        http_post=lambda url, body: _facet_payload("07", [])
    )
    assert "organization_id" not in result
    assert result["fabricated"] is not True
