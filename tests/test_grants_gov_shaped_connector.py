from nativeforge.services.source_connectors.grants_gov_shaped import (
    grants_gov_like_to_fixture_row,
)


def test_grants_gov_aliases_title_agency() -> None:
    raw = {
        "title": "Example tribal broadband NOFO",
        "agencyName": "Illustrative NTIA",
        "OpportunityNumber": "GG-SAMPLE-001",
        "OpportunityURL": "https://example.test/grants/sample",
    }
    out = grants_gov_like_to_fixture_row(raw)
    assert out["opportunity_title"] == "Example tribal broadband NOFO"
    assert out["agency"] == "Illustrative NTIA"
    assert out["opportunity_number"] == "GG-SAMPLE-001"
