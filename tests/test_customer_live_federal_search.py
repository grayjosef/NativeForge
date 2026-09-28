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
    assert result["collectors_live"] is False
    assert result["search_live"] is True
    assert result["result_count"] == 1
    row = result["results"][0]
    assert row["title"] == "Tribal public health capacity"
    assert row["native_relevance_decided"] is False
    assert row["source"] == "grants.gov"
    assert "publisher" in row["why_it_matches"].lower()


def test_unrelated_org_is_not_in_payload() -> None:
    result = search_live_federal_opportunities(
        http_post=lambda url, body: _facet_payload("07", [])
    )
    assert "organization_id" not in result
    assert result["fabricated"] is not True
