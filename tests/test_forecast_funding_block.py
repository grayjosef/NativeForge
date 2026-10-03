"""A forecast's money is in the forecast block, and we were not reading it.

Grants.gov publishes a posted notice under `synopsis` and a forecast under
`forecast`. `build_fetch_opportunity_funding_record` only ever read
`synopsis`, so every forecast record resolved to funding_semantic NONE
regardless of what the publisher had published.

Measured on 2026-10-03: of 200 active opportunities, 85 were forecasts and
not one of them could ever gain a value. A full bounded re-enrichment that
day fetched 200 details, succeeded 200 times, parsed 200 with zero failures,
and moved known value from 31 to 31 - a pipeline working perfectly while
being pointed at the wrong block for 42% of the corpus.

The field names in the forecast block are a HYPOTHESIS. The committed
fetchOpportunity fixture is a synopsis record and carries no forecast block,
so nothing in this repository evidences them. That is safe to hold here
because the fallback cannot invent a value: absent or differently named
fields return NONE exactly as before. `funding_block` records which block
answered so production settles the question.
"""

from __future__ import annotations

from nativeforge.services.grants_gov_synopsis_funding_service import (
    build_fetch_opportunity_funding_record,
)


def _record(detail: dict) -> dict:
    return build_fetch_opportunity_funding_record(
        detail=detail,
        opportunity_number="TEST-1",
        source_record_id="1",
        doc_type="synopsis",
        lifecycle_status="posted",
    )


def test_a_synopsis_value_is_still_read_from_the_synopsis():
    """The existing path must not change. 31 records depend on it."""
    r = _record({"synopsis": {"estimatedFunding": "6800000"}})
    assert r["funding_amount_min"] == "6800000"
    assert r["funding_enrichment_meta"]["funding_block"] == "synopsis"


def test_a_forecast_value_is_read_from_the_forecast_block():
    r = _record({"forecast": {"estimatedFunding": "125000000"}})
    assert r["funding_amount_min"] == "125000000"
    assert r["funding_enrichment_meta"]["funding_block"] == "forecast"
    assert r["funding_enrichment_meta"]["funding_semantic"] == "PROGRAM_TOTAL_POINT"


def test_the_synopsis_wins_when_both_carry_a_value():
    """The forecast is a fallback, not a competitor. A posted notice is the
    more authoritative statement of what is actually on offer."""
    r = _record(
        {
            "synopsis": {"estimatedFunding": "1000"},
            "forecast": {"estimatedFunding": "999999"},
        }
    )
    assert r["funding_amount_min"] == "1000"
    assert r["funding_enrichment_meta"]["funding_block"] == "synopsis"


def test_nothing_is_invented_when_neither_block_has_money():
    """The whole safety of the hypothesis rests on this.

    A truthful UNKNOWN is preferable to a fabricated dollar amount.
    """
    for detail in ({}, {"synopsis": {}}, {"forecast": {}}, {"synopsis": {}, "forecast": {}}):
        r = _record(detail)
        assert "funding_amount_min" not in r, detail
        assert "funding_amount_max" not in r, detail
        assert r["funding_enrichment_meta"]["funding_semantic"] == "NONE", detail


def test_unknown_forecast_field_names_degrade_to_none_rather_than_guessing():
    """If Grants.gov names forecast fields differently, we learn that as a
    NONE - never as a number scraped from whatever was nearby."""
    r = _record({"forecast": {"totalProgramFunding": "500000", "ceiling": "100"}})
    assert "funding_amount_min" not in r
    assert r["funding_enrichment_meta"]["funding_semantic"] == "NONE"


def test_a_forecast_ceiling_alone_is_carried_as_a_ceiling():
    """I wrote this test hours before the contract changed, asserting that a
    ceiling alone stays NONE. Mayhem then set the standard that an award
    ceiling IS monetary intelligence, so the assertion is restated rather
    than deleted - and it still pins the part that matters: no invented
    floor, and the ceiling semantic is preserved rather than flattened.
    """
    r = _record({"forecast": {"awardCeiling": "450000"}})
    assert "funding_amount_min" not in r
    assert r["funding_amount_max"] == "450000"
    assert r["funding_enrichment_meta"]["funding_semantic"] == "AWARD_CEILING_ONLY"
