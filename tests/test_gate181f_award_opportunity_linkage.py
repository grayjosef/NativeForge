"""Gate 181F — an award is evidence that money moved, and nothing more.

The whole gate is one refusal: a shared assistance listing is not a shared
opportunity. One programme produces annual competitions, discretionary rounds
and supplements, and merging on it would let NativeForge tell a Tribe it
missed a specific grant it may never have been able to apply for.

Offline and pure. The live contract proof is separate and reported as such.
"""

from __future__ import annotations

from nativeforge.services.award_opportunity_linkage_service import (
    AMBIGUOUS,
    CONFIRMED_LINK,
    MISS_INVESTIGATE,
    MISS_NONE,
    MISS_REVIEW,
    MISS_STRONG,
    MISS_UNKNOWN,
    NO_LINK,
    PROGRAM_LEVEL_ONLY,
    RECOGNITION_UNKNOWN,
    UNKNOWN,
    build_award_identity,
    build_recipient_evidence,
    classify_award_linkage,
    classify_miss_signal,
    native_relevance_evidence,
    program_recurrence_evidence,
)

ALN = "15.031"

OPP_2026 = {
    "canonical_id": "L1:BIA-2026-TTGP|synopsis",
    "opportunity_number": "BIA-2026-TTGP",
    "assistance_listing": ALN,
    "awarding_agency_code": "DOI-BIA",
}
OPP_2027 = {
    "canonical_id": "L1:BIA-2027-TTGP|synopsis",
    "opportunity_number": "BIA-2027-TTGP",
    "assistance_listing": ALN,
    "awarding_agency_code": "DOI-BIA",
}


def award(**kw):
    base = {
        "publisher_award_id": "ASST_NON_15031_2026_0001",
        "recipient_key": "9cca2ade-ca69-1b70-ce70-60f8c6efc6d5-C",
        "recipient_name": "NAVAJO NATION TRIBAL GOVERNMENT",
        "assistance_listing": ALN,
        "awarding_agency_code": "DOI-BIA",
        "award_amount": 3333334.0,
        "action_date": "2026-03-01",
        "fiscal_year": "2026",
    }
    base.update(kw)
    return base


# ---- 1. award identity ------------------------------------------------


def test_1_publisher_award_id_is_the_identity():
    identity = build_award_identity(award())
    assert identity["award_key"] == "ASST_NON_15031_2026_0001"
    assert identity["identity_basis"] == "publisher_award_id"
    assert identity["identity_is_publisher_issued"] is True
    assert identity["identity_is_composite_fallback"] is False


def test_1_a_composite_fallback_says_it_is_one():
    """Recipient+amount+date breaks the moment an amount is corrected."""
    identity = build_award_identity(award(publisher_award_id=None))
    assert identity["identity_is_publisher_issued"] is False
    assert identity["composite_fallback_is_low_confidence"] is True


# ---- 3/19. THE false merge this gate exists to prevent -----------------


def test_3_same_assistance_listing_is_program_level_only():
    result = classify_award_linkage(award=award(), candidate_opportunities=[OPP_2026])
    assert result["linkage"] == PROGRAM_LEVEL_ONLY
    assert result["linked_canonical_id"] is None
    assert result["may_link_automatically"] is False
    assert result["assistance_listing_is_not_opportunity_identity"] is True


def test_19_one_listing_across_two_solicitations_links_to_neither():
    """Two fiscal years of one programme. The award belongs to one of them and
    the assistance listing cannot say which."""
    result = classify_award_linkage(
        award=award(), candidate_opportunities=[OPP_2026, OPP_2027]
    )
    assert result["linkage"] == PROGRAM_LEVEL_ONLY
    assert result["linked_canonical_id"] is None
    assert result["program_matched_canonical_ids"] == sorted(
        [OPP_2026["canonical_id"], OPP_2027["canonical_id"]]
    )


def test_3_agreeing_agency_does_not_promote_a_program_match():
    """Same programme AND same agency is still not the same solicitation."""
    result = classify_award_linkage(award=award(), candidate_opportunities=[OPP_2026])
    assert "awarding_agency_also_agrees" in result["reasons"]
    assert result["linkage"] == PROGRAM_LEVEL_ONLY


# ---- 4/5/6. the grades ------------------------------------------------


def test_4_a_named_opportunity_number_is_a_confirmed_link():
    result = classify_award_linkage(
        award=award(opportunity_number="BIA-2026-TTGP"),
        candidate_opportunities=[OPP_2026, OPP_2027],
    )
    assert result["linkage"] == CONFIRMED_LINK
    assert result["linked_canonical_id"] == OPP_2026["canonical_id"]
    assert result["may_link_automatically"] is True


def test_5_several_records_for_one_number_is_ambiguous():
    twin = dict(OPP_2027, opportunity_number="BIA-2026-TTGP")
    result = classify_award_linkage(
        award=award(opportunity_number="BIA-2026-TTGP"),
        candidate_opportunities=[OPP_2026, twin],
    )
    assert result["linkage"] == AMBIGUOUS
    assert result["linked_canonical_id"] is None
    assert result["may_link_automatically"] is False


def test_6_no_identifier_at_all_is_unknown():
    result = classify_award_linkage(
        award=award(assistance_listing=None), candidate_opportunities=[OPP_2026]
    )
    assert result["linkage"] == UNKNOWN
    assert result["linked_canonical_id"] is None


def test_probable_link_is_never_machine_actionable():
    from nativeforge.services.award_opportunity_linkage_service import (
        MACHINE_LINKABLE,
        PROBABLE_LINK,
    )

    assert PROBABLE_LINK not in MACHINE_LINKABLE
    assert MACHINE_LINKABLE == {CONFIRMED_LINK}


# ---- 7. no fake opportunities -----------------------------------------


def test_7_an_award_never_creates_an_opportunity():
    for candidates in ([], [OPP_2026], None):
        result = classify_award_linkage(
            award=award(), candidate_opportunities=candidates
        )
        assert result["award_never_creates_an_opportunity"] is True
        assert "created_canonical_id" not in result
        # Nothing is returned that a caller could mistake for a new record.
        assert result["linked_canonical_id"] is None


def test_7_an_award_with_no_candidates_is_still_valid_evidence():
    result = classify_award_linkage(award=award(), candidate_opportunities=[])
    assert result["linkage"] == PROGRAM_LEVEL_ONLY
    assert result["program_matched_canonical_ids"] == []


# ---- 10/11/12. miss detection -----------------------------------------


def test_10_a_named_solicitation_we_never_saw_is_a_strong_miss():
    linkage = classify_award_linkage(
        award=award(opportunity_number="BIA-2026-GHOST"),
        candidate_opportunities=[OPP_2026],
    )
    assert linkage["linkage"] == NO_LINK
    signal = classify_miss_signal(linkage=linkage, solicitation_observed=False)
    assert signal["miss_signal"] == MISS_STRONG
    assert signal["is_confirmed_miss"] is True


def test_11_program_level_evidence_is_a_clue_not_a_confirmed_miss():
    """The exaggeration this gate refuses."""
    linkage = classify_award_linkage(award=award(), candidate_opportunities=[OPP_2026])
    signal = classify_miss_signal(linkage=linkage, solicitation_observed=False)
    assert signal["miss_signal"] == MISS_INVESTIGATE
    assert signal["is_confirmed_miss"] is False


def test_12_a_solicitation_already_in_the_graph_is_not_a_miss():
    linkage = classify_award_linkage(
        award=award(opportunity_number="BIA-2026-TTGP"),
        candidate_opportunities=[OPP_2026],
    )
    signal = classify_miss_signal(linkage=linkage, solicitation_observed=True)
    assert signal["miss_signal"] == MISS_NONE
    assert signal["is_confirmed_miss"] is False


def test_ambiguous_linkage_is_review_not_a_miss():
    twin = dict(OPP_2027, opportunity_number="BIA-2026-TTGP")
    linkage = classify_award_linkage(
        award=award(opportunity_number="BIA-2026-TTGP"),
        candidate_opportunities=[OPP_2026, twin],
    )
    signal = classify_miss_signal(linkage=linkage, solicitation_observed=False)
    assert signal["miss_signal"] == MISS_REVIEW
    assert signal["is_confirmed_miss"] is False


def test_unknown_linkage_cannot_produce_a_miss():
    linkage = classify_award_linkage(
        award=award(assistance_listing=None), candidate_opportunities=[]
    )
    signal = classify_miss_signal(linkage=linkage, solicitation_observed=False)
    assert signal["miss_signal"] == MISS_UNKNOWN
    assert signal["is_confirmed_miss"] is False


# ---- 2/20. recipient identity is not tenant identity -------------------


def test_2_recipient_evidence_is_preserved_without_a_tenant_link():
    evidence = build_recipient_evidence(award())
    assert evidence["recipient_key"] == "9cca2ade-ca69-1b70-ce70-60f8c6efc6d5-C"
    assert evidence["recipient_name"] == "NAVAJO NATION TRIBAL GOVERNMENT"
    assert evidence["recipient_key_is_publisher_issued"] is True
    assert evidence["tenant_organization_id"] is None
    assert evidence["tenant_link_basis"] == "NOT_LINKED"


def test_20_a_similar_name_creates_no_tenant_association():
    """'Cherokee Nation' names one government and several unrelated bodies."""
    evidence = build_recipient_evidence(
        award(recipient_name="CHEROKEE NATION", recipient_key="other-key")
    )
    assert evidence["tenant_organization_id"] is None
    assert evidence["tenant_link_basis"] == "NOT_LINKED"


# ---- 9. recognition class ---------------------------------------------


def test_9_recognition_class_is_unknown_from_award_data_alone():
    """Inferring 'federally recognized' from a name is a legal claim made by
    string matching."""
    evidence = build_recipient_evidence(award())
    assert evidence["recognition_class"] == RECOGNITION_UNKNOWN
    assert "federally recognized" in evidence["recognition_class_reason"]


# ---- 8. relevance, not eligibility ------------------------------------


def test_8_prior_native_awards_support_relevance_only():
    evidence = native_relevance_evidence([award(), award(fiscal_year="2025")])
    assert evidence["supports_relevance"] is True
    assert evidence["evidence_kind"] == "PRIOR_AWARD_HISTORY"
    assert evidence["determines_eligibility"] is False
    assert evidence["eligibility_requires_current_evidence"] is True
    assert evidence["programs_with_prior_awards"] == [ALN]


def test_8_no_prior_awards_supports_nothing_either_way():
    evidence = native_relevance_evidence([])
    assert evidence["supports_relevance"] is False
    assert evidence["determines_eligibility"] is False


# ---- 13. recurrence ---------------------------------------------------


def test_13_program_recurrence_is_not_opportunity_recurrence():
    evidence = program_recurrence_evidence(
        [
            award(fiscal_year="2024"),
            award(fiscal_year="2025"),
            award(fiscal_year="2026"),
        ]
    )
    assert evidence["program_recurrence_observed"] is True
    assert evidence["fiscal_years_with_awards"] == ["2024", "2025", "2026"]
    # The claim that must never be made from award data.
    assert evidence["opportunity_recurrence_observed"] is False
    assert "do not carry the solicitation" in evidence["opportunity_recurrence_reason"]


def test_13_a_single_year_is_not_recurrence():
    evidence = program_recurrence_evidence([award(fiscal_year="2026")])
    assert evidence["program_recurrence_observed"] is False


# ---- 14. replay -------------------------------------------------------


def test_14_the_same_award_observed_twice_has_one_identity():
    first = build_award_identity(award())
    second = build_award_identity(award())
    assert first == second
    assert first["award_key"] == second["award_key"]


def test_14_classification_is_deterministic():
    a = classify_award_linkage(award=award(), candidate_opportunities=[OPP_2026])
    b = classify_award_linkage(award=award(), candidate_opportunities=[OPP_2026])
    assert a == b


# ---- 15. award updates ------------------------------------------------


def test_15_a_changed_amount_keeps_the_same_publisher_identity():
    """History is retained because identity does not move with the amount."""
    original = build_award_identity(award(award_amount=3333334.0))
    corrected = build_award_identity(award(award_amount=4000000.0))
    assert original["award_key"] == corrected["award_key"]


def test_15_a_composite_identity_would_have_broken():
    """Why publisher identity matters: the fallback does move."""
    original = build_award_identity(
        award(publisher_award_id=None, award_amount=3333334.0)
    )
    corrected = build_award_identity(
        award(publisher_award_id=None, award_amount=4000000.0)
    )
    assert original["award_key"] != corrected["award_key"]


# ---- genericity -------------------------------------------------------


def test_the_linkage_layer_names_no_publisher():
    import ast
    import inspect

    from nativeforge.services import award_opportunity_linkage_service as svc

    tree = ast.parse(inspect.getsource(svc))
    names: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            names.append(node.id)
        elif isinstance(node, ast.Attribute):
            names.append(node.attr)
        elif isinstance(node, ast.ImportFrom):
            names.append(node.module or "")
    haystack = " ".join(names).lower()
    for leak in ("usaspending", "grants_gov", "search2", "generated_internal_id"):
        assert leak not in haystack, f"publisher-specific identifier: {leak}"


def test_every_grade_has_a_defined_meaning():
    from nativeforge.services.award_opportunity_linkage_service import (
        LINKAGE_GRADES,
    )

    assert len(set(LINKAGE_GRADES)) == len(LINKAGE_GRADES) == 6
    assert UNKNOWN in LINKAGE_GRADES
    assert PROGRAM_LEVEL_ONLY in LINKAGE_GRADES
