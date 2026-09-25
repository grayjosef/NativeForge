"""Gate 182E — "there is money for this" is not "apply here".

Measured live on one federal environmental publisher's Tribal programmes,
2026-09-25. Five programme pages, five channels:

    wastewater set-aside   EXTERNAL_AGENCY_QUEUE   -> enter another agency's
                                                     system; no application
                                                     exists at the funder
    drinking water set-aside FORMULA_ALLOCATION    -> await allocation
    nonpoint source        DIRECT + FORMULA        -> apply (and a base grant
                                                     by formula on one page)
    capacity programme     DIRECT                  -> apply
    funding hub            (a roster, not a programme)

Two of five are directly applicable. Three are real money nobody applies for
at this agency. Those counts are dated observations and appear in no
assertion.

Offline.
"""

from __future__ import annotations

import pytest

from nativeforge.services.funding_channel_service import (
    ACTION_APPLY,
    ACTION_AWAIT_ALLOCATION,
    ACTION_CONTACT_ADMINISTRATOR,
    ACTION_ENTER_EXTERNAL_QUEUE,
    ACTION_UNKNOWN,
    CHANNEL_UNKNOWN,
    DIRECT_FEDERAL_APPLICATION,
    EXTERNAL_AGENCY_QUEUE,
    FORMULA_ALLOCATION,
    REGIONAL_OFFICE_ALLOCATION,
    REVOLVING_LOAN_FUND,
    STATE_ADMINISTERED,
    classify_funding_channel,
    detect_channels,
    summarize_channels,
)

# Real sentences from the measured pages, kept verbatim because the whole
# point is that they are what publishers actually write.
WASTEWATER = (
    "To be considered for programme funding, Tribes must identify their "
    "wastewater needs to the Sanitation Deficiency System. The agency uses "
    "the Sanitation Deficiency System priority lists to identify projects. "
    "The programme incorporates concepts adopted by the Clean Water State "
    "Revolving Fund."
)
DRINKING_WATER = (
    "Any federally recognized Tribe is eligible to receive a grant. The "
    "agency uses formulas to allocate programme funds among the Regional "
    "Offices annually. The Act authorized the agency to set-aside up to 1.5% "
    "of the State Revolving Fund."
)
NONPOINT = (
    "Please note that applicants must submit applications via the federal "
    "portal. The FY26 Tribal Competitive Notice of Funding Opportunity is now "
    "open. Proposed base grant work plan deadlines vary by Region; please "
    "contact your Region for more details. The revised base grant allocation "
    "formula is outlined below."
)


# ---- the case that costs a funding cycle ------------------------------


def test_the_funder_holding_the_money_does_not_mean_it_takes_the_application():
    """The page belongs to the funder, mentions grants, and has no
    application. "Apply here" would send a Tribe to a competition that does
    not exist while it misses the queue that actually allocates the money."""
    result = classify_funding_channel(WASTEWATER, funder="the publisher")
    assert result["funding_channel"] == EXTERNAL_AGENCY_QUEUE
    assert result["customer_action"] == ACTION_ENTER_EXTERNAL_QUEUE
    assert result["directly_applicable"] is False


def test_an_external_queue_outranks_every_other_signal_on_the_page():
    """It is the one a reader is most likely to get wrong."""
    assert EXTERNAL_AGENCY_QUEUE in detect_channels(WASTEWATER)
    assert REVOLVING_LOAN_FUND in detect_channels(WASTEWATER)
    assert classify_funding_channel(WASTEWATER)["funding_channel"] == (
        EXTERNAL_AGENCY_QUEUE
    )


def test_the_application_authority_is_never_inferred_from_the_funder():
    result = classify_funding_channel(WASTEWATER, funder="agency A")
    assert result["application_authority"] is None
    assert result["application_authority_established"] is False
    assert result["funder_is_not_automatically_the_application_authority"] is True


def test_a_differing_authority_is_recorded_as_a_reason():
    result = classify_funding_channel(
        WASTEWATER, funder="agency A", application_authority="agency B"
    )
    assert "application_authority_differs_from_funder" in result["reasons"]
    assert result["application_authority_established"] is True


# ---- a mention of a mechanism is not that mechanism -------------------


def test_a_set_aside_carved_from_a_revolving_fund_is_not_a_loan_programme():
    """Ranking the fund first read the statutory parent as the channel and
    told a Tribe to go and talk to a loan programme."""
    result = classify_funding_channel(DRINKING_WATER)
    assert result["funding_channel"] == FORMULA_ALLOCATION
    assert result["customer_action"] == ACTION_AWAIT_ALLOCATION
    assert REVOLVING_LOAN_FUND in result["channels_detected"]


def test_formula_money_is_awaited_not_applied_for():
    result = classify_funding_channel("Funds are allocated by formula annually.")
    assert result["customer_action"] == ACTION_AWAIT_ALLOCATION
    assert result["directly_applicable"] is False


def test_a_genuine_revolving_fund_is_still_recognised():
    result = classify_funding_channel(
        "Assistance is provided through a revolving loan fund administered locally."
    )
    assert result["funding_channel"] == REVOLVING_LOAN_FUND
    assert result["customer_action"] == ACTION_CONTACT_ADMINISTRATOR


# ---- a direct application is a direct application ---------------------


def test_a_real_competition_says_apply():
    result = classify_funding_channel(NONPOINT)
    assert result["funding_channel"] == DIRECT_FEDERAL_APPLICATION
    assert result["customer_action"] == ACTION_APPLY
    assert result["directly_applicable"] is True


def test_one_page_may_carry_two_channels():
    """A competition and a formula base grant, on the same page. Flattening
    to one loses whichever the reader needed."""
    result = classify_funding_channel(NONPOINT)
    assert result["multiple_channels_detected"] is True
    assert DIRECT_FEDERAL_APPLICATION in result["channels_detected"]
    assert FORMULA_ALLOCATION in result["channels_detected"]
    assert REGIONAL_OFFICE_ALLOCATION in result["channels_detected"]


def test_a_state_administered_programme_routes_to_its_administrator():
    result = classify_funding_channel(
        "These funds are administered by the states; apply through your state agency."
    )
    assert result["funding_channel"] == STATE_ADMINISTERED
    assert result["customer_action"] == ACTION_CONTACT_ADMINISTRATOR
    assert result["directly_applicable"] is False


def test_a_state_channel_outranks_a_direct_sounding_phrase():
    """ "apply through your state" contains "apply"; the channel is the state."""
    result = classify_funding_channel(
        "Applications must be submitted through your state agency, which "
        "administers the programme."
    )
    assert result["funding_channel"] == STATE_ADMINISTERED


# ---- honest silence ---------------------------------------------------


def test_a_page_that_says_nothing_about_channel_is_unknown():
    result = classify_funding_channel(
        "This programme supports environmental work in communities."
    )
    assert result["funding_channel"] == CHANNEL_UNKNOWN
    assert result["customer_action"] == ACTION_UNKNOWN
    assert result["directly_applicable"] is False


@pytest.mark.parametrize("empty", [None, "", "   "])
def test_empty_input_is_unknown_not_applicable(empty):
    result = classify_funding_channel(empty)
    assert result["funding_channel"] == CHANNEL_UNKNOWN
    assert result["directly_applicable"] is False


def test_unknown_never_says_apply():
    assert classify_funding_channel(None)["customer_action"] != ACTION_APPLY


# ---- channel is not eligibility and not relevance ---------------------


def test_channel_decides_neither_eligibility_nor_relevance():
    result = classify_funding_channel(NONPOINT)
    assert result["eligibility_decided"] is False
    assert result["native_relevance_decided"] is False


def test_every_result_carries_the_refusal():
    assert classify_funding_channel(NONPOINT)["money_exists_is_not_apply_here"] is True


# ---- the plural / stem regression class -------------------------------


@pytest.mark.parametrize(
    "phrase",
    [
        "submit application via the portal",
        "submit applications via the portal",
        "applications must be submitted",
        "application must be submitted",
        "see the Notice of Funding Opportunity",
        "see the Notice of Funding Opportunities",
        "NOFO is now open",
        "NOFOs are now open",
    ],
)
def test_direct_application_matches_both_numbers(phrase):
    """A trailing \\b has hidden real money three times in this campaign."""
    assert DIRECT_FEDERAL_APPLICATION in detect_channels(phrase)


@pytest.mark.parametrize(
    "phrase",
    [
        "the allocation formula is published",
        "allocation formulas are published",
        "formula allocation for this year",
        "formula allocations for this year",
    ],
)
def test_formula_matches_both_numbers(phrase):
    assert FORMULA_ALLOCATION in detect_channels(phrase)


@pytest.mark.parametrize(
    "phrase", ["the Regional Office allocates", "Regional Offices allocate"]
)
def test_regional_matches_both_numbers(phrase):
    assert REGIONAL_OFFICE_ALLOCATION in detect_channels(phrase)


# ---- falsifiability ---------------------------------------------------


def test_the_detector_returns_nothing_when_there_is_nothing():
    assert detect_channels("A general description of environmental work.") == []


def test_the_detector_distinguishes_its_channels():
    assert detect_channels("applications must be submitted") == [
        DIRECT_FEDERAL_APPLICATION
    ]
    assert detect_channels("administered by the states") == [STATE_ADMINISTERED]


def test_replay_is_deterministic():
    assert classify_funding_channel(WASTEWATER) == classify_funding_channel(WASTEWATER)


# ---- the summary that stops a roster reading as a to-do list ----------


def test_the_summary_separates_records_from_applications():
    entries = [
        classify_funding_channel(WASTEWATER),
        classify_funding_channel(DRINKING_WATER),
        classify_funding_channel(NONPOINT),
        classify_funding_channel("submit applications via the portal"),
        classify_funding_channel("A general description."),
    ]
    summary = summarize_channels(entries)
    assert summary["record_count"] == 5
    assert summary["directly_applicable_count"] == 2
    assert summary["not_directly_applicable"] == 3
    assert summary["by_customer_action"][ACTION_ENTER_EXTERNAL_QUEUE] == 1
    assert summary["by_customer_action"][ACTION_AWAIT_ALLOCATION] == 1
    assert summary["record_count_is_not_application_count"] is True


def test_an_empty_portfolio_summarises_to_zero():
    summary = summarize_channels([])
    assert summary["record_count"] == 0
    assert summary["directly_applicable_count"] == 0


# ---- genericity -------------------------------------------------------


def test_the_channel_reader_names_no_agency():
    import ast
    import inspect

    from nativeforge.services import funding_channel_service as svc

    tree = ast.parse(inspect.getsource(svc))
    names: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            names.append(node.id)
        elif isinstance(node, ast.Attribute):
            names.append(node.attr)
        elif isinstance(node, ast.ImportFrom):
            names.append(node.module or "")
        elif isinstance(node, ast.FunctionDef):
            names.append(node.name)
    haystack = " ".join(names).lower()
    for leak in ("epa", "ihs", "hud", "cwisa", "dwig", "grants_gov", "sanitation"):
        assert leak not in haystack, f"publisher-specific identifier: {leak}"
