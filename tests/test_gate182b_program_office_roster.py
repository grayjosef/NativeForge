"""Gate 182B — a programme office is a roster, not a pipeline.

Measured live on a real Native-serving programme office, 2026-09-25. Its eight
published programmes:

    3  carry competitive signals -> referred to the canonical source
    2  formula allocation        -> real money, nothing to apply for
    2  loan guarantee            -> not a grant at all
    1  policy/notice index

and the office publishes ZERO opportunity records of its own. Its two
programme pages that do link to opportunities linked to competitions that had
already closed, while the live forecasts for the current cycle were not linked
at all.

Offline. The live measurement is reported separately.
"""

from __future__ import annotations

import pytest

from nativeforge.services.program_office_roster_service import (
    COMPETITIVE_GRANT,
    FORMULA_ALLOCATION,
    LOAN_GUARANTEE,
    POLICY_GUIDANCE,
    PROGRAM_INFORMATION,
    RECORD_KIND_ANNOUNCEMENT,
    RECORD_KIND_PROGRAM,
    REFERENCE_CURRENT,
    REFERENCE_HISTORICAL,
    REFERENCE_SUPERSEDED,
    REFERENCE_UNKNOWN,
    ROUTE_CANONICAL_REFERRAL,
    ROUTE_FINANCIAL_ASSISTANCE,
    ROUTE_FORMULA_INTELLIGENCE,
    ROUTE_INTELLIGENCE,
    TECHNICAL_ASSISTANCE,
    TRAINING_EVENT,
    VEHICLE_UNKNOWN,
    build_program_identity,
    classify_funding_vehicle,
    classify_opportunity_reference,
    detect_vehicle_signals,
    summarize_roster,
)


def prog(title, description="", **kw):
    return classify_funding_vehicle({"title": title, "description": description}, **kw)


# ---- formula money is real money and is not pursuable -----------------


def test_a_formula_programme_is_not_an_opportunity():
    """The largest single source of Indian housing assistance. Not pursuable."""
    result = prog(
        "Indian Housing Block Grant Program",
        "Funds appropriated by Congress are made available to eligible grant "
        "recipients through a formula.",
    )
    assert result["funding_vehicle"] == FORMULA_ALLOCATION
    assert result["route"] == ROUTE_FORMULA_INTELLIGENCE
    assert result["may_bear_opportunity"] is False
    assert result["formula_money_is_not_pursuable"] is True


def test_formula_money_never_reaches_the_opportunity_graph():
    result = prog("Annual Allocation Notice", "allocated annually, no competition")
    assert result["route"] != ROUTE_CANONICAL_REFERRAL


# ---- the competitive/formula collision, measured ----------------------


def test_a_competitive_programme_for_formula_recipients_is_competitive():
    """The real trap: this programme's own words contain "Formula".

    Checking formula language first classifies a $125M competition as formula
    money and drops it out of the referral path entirely.
    """
    result = prog(
        "Indian Housing Block Grant Competitive",
        "IHBG-COMP provides competitive grant opportunities to eligible IHBG "
        "Formula recipients.",
    )
    assert result["funding_vehicle"] == COMPETITIVE_GRANT
    assert result["route"] == ROUTE_CANONICAL_REFERRAL
    assert result["may_bear_opportunity"] is True
    assert FORMULA_ALLOCATION in result["vehicle_signals"]


def test_competitive_evidence_deep_in_a_description_is_still_found():
    """The real page put "Notice of Funding Opportunity" at character 718.

    A probe that truncated the description at 700 characters classified a
    programme with a live $90M forecast as PROGRAM_INFORMATION. The instrument
    was the bug, and the classifier must not reward a short read.
    """
    padding = "General programme description. " * 30
    result = prog(
        "Indian Community Development Block Grant Program",
        padding + "Single purpose grants are awarded on a competition basis "
        "pursuant to the terms published in an annual Notice of Funding "
        "Opportunity (NOFO).",
    )
    assert result["funding_vehicle"] == COMPETITIVE_GRANT
    assert result["may_bear_opportunity"] is True


# ---- the trailing word boundary, refusing to happen a third time ------


@pytest.mark.parametrize("word", ["NOFO", "NOFOs", "NOFA", "NOFAs", "nofos"])
def test_the_acronyms_match_their_plurals(word):
    """A real page read "in all applicable program NOFOs".

    `\\bnofo\\b` refuses that, silently, exactly as the closing boundary in the
    Federal Register funding pattern classified two real funding notices as
    OTHER. Same bug, new module, caught before shipping.
    """
    assert COMPETITIVE_GRANT in detect_vehicle_signals(
        {"title": "Programme", "description": f"see applicable program {word}"}
    )


# ---- loans are not grants ---------------------------------------------


@pytest.mark.parametrize(
    "title,desc",
    [
        ("Section 184 Loan Guarantee", "a home mortgage product for Native families"),
        ("Title VI Loan Guarantee Program", "guaranteed loan for tribal housing"),
    ],
)
def test_a_loan_guarantee_is_not_a_grant(title, desc):
    result = prog(title, desc)
    assert result["funding_vehicle"] == LOAN_GUARANTEE
    assert result["route"] == ROUTE_FINANCIAL_ASSISTANCE
    assert result["may_bear_opportunity"] is False


def test_loan_programmes_never_enter_the_opportunity_graph():
    """Measured: both loan programmes return zero records on the canonical
    grant source, because they are not grants."""
    result = prog("Loan Guarantee Program", "lender and borrower requirements")
    assert result["route"] != ROUTE_CANONICAL_REFERRAL


# ---- services are not money -------------------------------------------


def test_technical_assistance_is_a_resource_not_an_opportunity():
    result = prog(
        "On-Call Technical Assistance",
        "Tribes can request up to 2 hours of targeted, direct technical "
        "assistance at no cost.",
    )
    assert result["funding_vehicle"] == TECHNICAL_ASSISTANCE
    assert result["may_bear_opportunity"] is False


def test_a_training_announcement_about_a_loan_programme_is_training():
    """Real announcement. Precedence tuned for programmes calls this a loan."""
    result = prog(
        "2nd Annual Underwriter's Boot Camp of the Section 184 Indian Housing "
        "Loan Guarantee Program",
        "Register here. The deadline for R.S.V.P is August 21.",
        record_kind=RECORD_KIND_ANNOUNCEMENT,
    )
    assert result["funding_vehicle"] == TRAINING_EVENT
    assert LOAN_GUARANTEE in result["vehicle_signals"]


def test_a_loan_programme_page_mentioning_training_is_still_a_loan_programme():
    """The same two signals, the other record kind, the other answer."""
    result = prog(
        "Title VI Loan Guarantee Program",
        "Dear Lender Letter. Register here for the upcoming workshop.",
        record_kind=RECORD_KIND_PROGRAM,
    )
    assert result["funding_vehicle"] == LOAN_GUARANTEE
    assert TRAINING_EVENT in result["vehicle_signals"]


def test_a_notice_listing_an_affected_loan_programme_is_still_a_notice():
    """Real announcement. It lists the programmes a policy change affects.

    Ranking loan above policy for announcements filed an income-calculation
    notice in the financial-assistance lane - the "a notice about a programme
    is not that programme" error, in its fifth costume.
    """
    result = prog(
        "Grantees Must Exclude Service-Connected Disability Compensation "
        "When Calculating Annual Income",
        "This applies to programmes under section 4(9)(C), including the "
        "Indian Housing Block Grant program, Title VI Loan Guarantee program, "
        "and the Tribal HUD-VASH program.",
        record_kind=RECORD_KIND_ANNOUNCEMENT,
    )
    assert result["funding_vehicle"] == POLICY_GUIDANCE
    assert result["route"] == ROUTE_INTELLIGENCE
    assert LOAN_GUARANTEE in result["vehicle_signals"]


def test_an_allocation_letter_is_formula_not_merely_a_letter():
    """The same record kind, the other way: a Dear Tribal Leader letter whose
    subject IS the allocation stays formula, which is what a Tribe needs."""
    result = prog(
        "FY 2027 Indian Housing Block Grant Formula Allocation Estimates",
        "The purpose of this Dear Tribal Leader letter is to inform Tribes of "
        "their formula allocation estimate for Fiscal Year 2027.",
        record_kind=RECORD_KIND_ANNOUNCEMENT,
    )
    assert result["funding_vehicle"] == FORMULA_ALLOCATION
    assert result["route"] == ROUTE_FORMULA_INTELLIGENCE


def test_record_kind_is_reported_so_the_reading_is_auditable():
    assert prog("x", "y")["record_kind"] == RECORD_KIND_PROGRAM


# ---- a programme page is not a programme ------------------------------


def test_a_page_covering_two_programmes_is_flagged_for_splitting():
    """Measured: one page covered a block grant AND a loan guarantee."""
    result = prog(
        "Native Hawaiian Programs",
        "The Native Hawaiian programs include the Native Hawaiian Housing "
        "Block Grant, allocated annually, and the Section 184A Native Hawaiian "
        "Housing Loan Guarantee.",
    )
    assert result["multiple_vehicles_detected"] is True
    assert result["requires_program_level_split"] is True
    assert len(result["vehicle_signals"]) > 1
    assert result["a_program_page_is_not_a_program"] is True


def test_a_single_vehicle_record_is_not_flagged():
    result = prog("Policy Guidance", "PIH Notice program guidance")
    assert result["multiple_vehicles_detected"] is False


def test_a_notice_index_is_policy_not_a_competition():
    """Measured: this programme's page is 1,693 characters of Dear Tribal
    Leader letters about RENEWAL applications, and both of its competitions on
    the canonical source are closed. A renewal is not an open competition."""
    result = prog(
        "Tribal Housing Programme",
        "Dear Tribal Leader Letters. PIH Notice procedural guidance for the "
        "FY26 Renewal Grant Application.",
    )
    assert result["funding_vehicle"] == POLICY_GUIDANCE
    assert result["route"] == ROUTE_INTELLIGENCE
    assert result["may_bear_opportunity"] is False


def test_a_competitive_signal_is_referred_even_when_it_loses_precedence():
    """The asymmetry. A false positive costs one referral; a false negative
    costs a Tribe money it never saw."""
    result = prog(
        "Boot Camp",
        "Register here. See the annual Notice of Funding Opportunity.",
        record_kind=RECORD_KIND_ANNOUNCEMENT,
    )
    assert result["funding_vehicle"] == TRAINING_EVENT
    assert result["may_bear_opportunity"] is True
    assert result["route"] == ROUTE_CANONICAL_REFERRAL


# ---- nothing here mints an opportunity --------------------------------


def test_even_a_competitive_programme_is_not_an_opportunity():
    result = prog("Competitive Grant Program", "competitive grant opportunities")
    assert result["may_bear_opportunity"] is True
    assert result["is_an_opportunity"] is False
    assert result["a_program_is_not_an_opportunity"] is True


def test_every_record_refuses_relevance_and_eligibility():
    result = prog("Indian Housing Block Grant", "competitive grant for tribes")
    assert result["native_relevance_decided"] is False
    assert result["eligibility_decided"] is False


def test_an_unnamed_record_is_unknown_not_a_guess():
    result = classify_funding_vehicle({"title": "", "description": ""})
    assert result["funding_vehicle"] == VEHICLE_UNKNOWN
    assert "no_vehicle_signal_found" in result["reasons"]


def test_a_named_programme_with_no_vehicle_evidence_says_so():
    result = prog("Some Programme Office Initiative", "")
    assert result["funding_vehicle"] == PROGRAM_INFORMATION
    assert result["route"] == ROUTE_INTELLIGENCE


# ---- programme identity is not opportunity identity -------------------


def test_the_assistance_listing_is_the_programme_key():
    identity = build_program_identity(
        {"title": "Indian Housing Block Grants", "assistance_listing": "14.867"}
    )
    assert identity["assistance_listing"] == "14.867"
    assert identity["program_key"] == "ALN:14.867"
    assert identity["program_identity_established"] is True


def test_a_programme_without_a_listing_is_unknown_not_slugged():
    identity = build_program_identity({"title": "Some Programme"})
    assert identity["assistance_listing"] is None
    assert identity["program_key"] is None
    assert identity["program_identity_established"] is False


def test_the_listing_survives_what_the_opportunity_number_does_not():
    """Three cycles, three numbering schemes, one stable programme key.

    FR-6800-N-48, FR-6900-N-48 and PIH-2600-DC-0048 are the same programme;
    keying on the opportunity number fuses or splits a decade of rounds.
    """
    keys = {
        build_program_identity({"title": t, "assistance_listing": "14.867"})[
            "program_key"
        ]
        for t in (
            "IHBG Competitive FY2024",
            "IHBG Competitive FY2025",
            "IHBG-COMP for FY 2026",
        )
    }
    assert keys == {"ALN:14.867"}


def test_identity_carries_the_distinction_it_exists_for():
    identity = build_program_identity({"title": "x", "assistance_listing": "14.862"})
    assert identity["program_identity_is_not_opportunity_identity"] is True


# ---- the stale-link guard, from the real pages ------------------------


def test_a_closed_link_with_a_newer_record_is_superseded():
    """The measured case: the page linked last year's closed competition while
    this year's forecast was not linked at all."""
    result = classify_opportunity_reference(
        referenced_status="closed",
        referenced_identifier="FR-6900-N-48",
        canonical_current_identifier="PIH-2600-DC-0048",
    )
    assert result["reference_currency"] == REFERENCE_SUPERSEDED
    assert result["showable_as_current"] is False


def test_a_two_year_old_link_is_also_superseded():
    result = classify_opportunity_reference(
        referenced_status="closed",
        referenced_identifier="FR-6800-N-48",
        canonical_current_identifier="PIH-2600-DC-0048",
    )
    assert result["reference_currency"] == REFERENCE_SUPERSEDED


def test_a_closed_link_with_no_newer_record_is_historical():
    result = classify_opportunity_reference(
        referenced_status="archived", referenced_identifier="FR-6300-N-48"
    )
    assert result["reference_currency"] == REFERENCE_HISTORICAL
    assert result["showable_as_current"] is False


def test_the_canonical_current_record_is_the_only_thing_shown_as_current():
    result = classify_opportunity_reference(
        referenced_status="posted",
        referenced_identifier="FR-6900-N-74",
        canonical_current_identifier="FR-6900-N-74",
    )
    assert result["reference_currency"] == REFERENCE_CURRENT
    assert result["showable_as_current"] is True


def test_an_open_link_that_is_not_the_canonical_record_is_superseded():
    result = classify_opportunity_reference(
        referenced_status="posted",
        referenced_identifier="OLD-1",
        canonical_current_identifier="NEW-2",
    )
    assert result["reference_currency"] == REFERENCE_SUPERSEDED


def test_an_unresolved_link_defaults_to_unknown_not_to_current():
    result = classify_opportunity_reference(
        referenced_status=None, referenced_identifier="FR-9999-N-99"
    )
    assert result["reference_currency"] == REFERENCE_UNKNOWN
    assert result["showable_as_current"] is False


def test_an_unrecognised_status_is_unknown():
    result = classify_opportunity_reference(referenced_status="banana")
    assert result["reference_currency"] == REFERENCE_UNKNOWN
    assert any("banana" in r for r in result["reasons"])


def test_every_reference_carries_the_refusal():
    result = classify_opportunity_reference(referenced_status="posted")
    assert result["a_page_link_is_not_proof_of_currency"] is True


# ---- the roster summary -----------------------------------------------


def test_the_summary_never_reports_a_roster_as_a_pipeline():
    entries = [
        prog("IHBG", "through a formula"),
        prog("IHBG Formula", "annual allocation"),
        prog("IHBG Competitive", "competitive grant opportunities"),
        prog("ICDBG", "annual Notice of Funding Opportunity"),
        prog("Native Hawaiian", "applicable program NOFOs"),
        prog("Section 184", "home loan guarantee"),
        prog("Title VI", "guaranteed loan"),
        prog("Tribal HUD-VASH", "PIH Notice program guidance"),
    ]
    summary = summarize_roster(entries)
    assert summary["program_count"] == 8
    assert summary["opportunity_bearing_count"] == 3
    assert summary["programs_that_are_not_pursuable"] == 5
    assert summary["opportunity_count_created_here"] == 0
    assert summary["program_count_is_not_opportunity_count"] is True


def test_the_summary_counts_verdicts_not_labels():
    """A record whose primary label is training can still bear a competition.

    Counting by label undercounted exactly that, and the undercount pointed at
    fewer opportunities than the routes said existed.
    """
    entries = [
        prog(
            "Boot Camp",
            "Register here. See the Notice of Funding Opportunity.",
            record_kind=RECORD_KIND_ANNOUNCEMENT,
        )
    ]
    summary = summarize_roster(entries)
    assert summary["by_funding_vehicle"][TRAINING_EVENT] == 1
    assert summary["opportunity_bearing_count"] == 1
    assert summary["by_route"][ROUTE_CANONICAL_REFERRAL] == 1


def test_an_empty_roster_summarises_to_zero_not_to_an_error():
    summary = summarize_roster([])
    assert summary["program_count"] == 0
    assert summary["opportunity_bearing_count"] == 0


def test_replay_is_deterministic():
    assert prog("IHBG Competitive", "competitive grant") == prog(
        "IHBG Competitive", "competitive grant"
    )


# ---- genericity -------------------------------------------------------


def test_the_roster_names_no_agency():
    import ast
    import inspect

    from nativeforge.services import program_office_roster_service as svc

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
    for leak in ("hud", "onap", "ihbg", "icdbg", "codetalk", "grants_gov"):
        assert leak not in haystack, f"publisher-specific identifier: {leak}"


def test_another_offices_field_names_work_unchanged():
    result = classify_funding_vehicle(
        {"programme": "Rural Loan Guarantee", "summary": "guaranteed loan"},
        field_map={"title": "programme", "description": "summary"},
    )
    assert result["funding_vehicle"] == LOAN_GUARANTEE
