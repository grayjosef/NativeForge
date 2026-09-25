"""Gate 182D — Native-serving is not Tribe-eligible.

Measured live on a wholly Native-serving health agency's current portfolio,
2026-09-25. Eighteen opportunities; the four its Tribal applicant-type codes
fail to index are:

    Tribal Epidemiology Centers   $7,000,000   "Tribes, Tribal Organizations,
                                                Urban Organizations"
    Urban Indian 4-in-1           $9,707,858   "IHS contracted UIOs"
    Urban Indian Educ. & Research $1,450,000   "AIAN National organization"
    National Urban Indian BH        $200,000   "must be a 501(c)(3)"

One of the four is open to Tribes. Three are not. Those figures are dated
observations and appear in no assertion; what is asserted is that the classes
stay distinct and that optimism is never the default.

Offline.
"""

from __future__ import annotations

import pytest

from nativeforge.services.native_entity_class_service import (
    AIAN_NATIONAL_ORGANIZATION,
    NAMED_NO,
    NAMED_UNKNOWN,
    NAMED_YES,
    NONPROFIT_501C3,
    TRIBAL_EPIDEMIOLOGY_CENTER,
    TRIBAL_ORGANIZATION,
    TRIBE_FEDERALLY_RECOGNIZED,
    TRIBE_RECOGNITION_UNSPECIFIED,
    TRIBE_STATE_RECOGNIZED,
    URBAN_INDIAN_ORGANIZATION,
    assess_tribal_applicant_class,
    extract_entity_classes,
    summarize_entity_classes,
)


def assess(prose, **kw):
    return assess_tribal_applicant_class(prose, **kw)


# ---- the four measured records ----------------------------------------


def test_tribes_tribal_organizations_urban_organizations_names_a_tribe():
    """The $7M record the Tribal codes miss. It IS open to Tribes."""
    result = assess("Tribes, Tribal Organizations, Urban Organizations")
    assert result["tribe_named_as_eligible_class"] == NAMED_YES
    assert TRIBE_RECOGNITION_UNSPECIFIED in result["entity_classes"]
    assert TRIBAL_ORGANIZATION in result["entity_classes"]
    assert URBAN_INDIAN_ORGANIZATION in result["entity_classes"]


def test_ihs_contracted_uios_names_no_tribe():
    """$9.7M, and a Tribe cannot apply for a penny of it."""
    result = assess("IHS contracted UIOs")
    assert URBAN_INDIAN_ORGANIZATION in result["entity_classes"]
    assert result["tribal_government_classes_named"] == []
    assert result["no_tribal_class_named"] is True
    assert result["tribe_named_as_eligible_class"] != NAMED_YES


def test_an_aian_national_organization_is_not_a_tribe():
    result = assess("AIAN National organization")
    assert AIAN_NATIONAL_ORGANIZATION in result["entity_classes"]
    assert result["no_tribal_class_named"] is True


def test_a_501c3_requirement_excludes_a_tribal_government():
    """ "must be" makes the list exhaustive, and a Tribe is not a 501(c)(3)."""
    result = assess(
        "To be eligible for this funding opportunity an applicant must be a "
        "501(c)(3) organization."
    )
    assert NONPROFIT_501C3 in result["entity_classes"]
    assert result["exclusive_language"] is True
    assert result["tribe_named_as_eligible_class"] == NAMED_NO


# ---- the guard this module exists for ---------------------------------


def test_a_native_serving_publisher_does_not_confer_eligibility():
    """Every opportunity here comes from an agency devoted to Native health.

    Three of the four its Tribal codes miss are closed to Tribes. Passing the
    agency's focus in must not move the answer one step.
    """
    with_focus = assess("IHS contracted UIOs", publisher_is_native_serving=True)
    without = assess("IHS contracted UIOs", publisher_is_native_serving=False)
    assert (
        with_focus["tribe_named_as_eligible_class"]
        == without["tribe_named_as_eligible_class"]
    )
    assert with_focus["publisher_native_focus_is_not_eligibility"] is True


def test_native_relevance_and_eligibility_stay_separate():
    result = assess("IHS contracted UIOs")
    assert result["native_relevant_evidence_present"] is True
    assert result["tribal_government_classes_named"] == []


def test_nothing_here_decides_relevance_or_tenant_eligibility():
    result = assess("Federally recognized Indian Tribes")
    assert result["native_relevance_decided"] is False
    assert result["tenant_eligibility_decided"] is False


# ---- three-valued, never optimistic -----------------------------------


def test_absent_prose_is_unknown_not_eligible():
    for prose in (None, "", "   "):
        assert assess(prose)["tribe_named_as_eligible_class"] == NAMED_UNKNOWN


def test_unreadable_prose_is_unknown_not_no():
    result = assess("See section 4 of the referenced authority.")
    assert result["tribe_named_as_eligible_class"] == NAMED_UNKNOWN
    assert result["no_tribal_class_named"] is False


def test_a_non_exclusive_list_without_a_tribe_is_unknown_not_no():
    """Absence from an illustrative list is not proof of exclusion."""
    result = assess("Applicants include Urban Indian Organizations.")
    assert result["exclusive_language"] is False
    assert result["tribe_named_as_eligible_class"] == NAMED_UNKNOWN


def test_an_exclusive_list_naming_a_tribe_is_yes():
    result = assess(
        "Eligible applicants are Tribes and Tribal organizations as described "
        "in the regulations."
    )
    assert result["tribe_named_as_eligible_class"] == NAMED_YES


# ---- recognition is a SEPARATE question -------------------------------


def test_federal_recognition_is_recorded_when_stated():
    result = assess("Federally recognized Indian Tribes are eligible.")
    assert result["federal_recognition"] == "FEDERAL_RECOGNITION_STATED"
    assert result["federal_recognition_stated"] is True
    assert result["tribe_named_as_eligible_class"] == NAMED_YES


def test_a_bare_tribe_names_a_tribe_but_states_no_recognition():
    """Most of the measured portfolio reads exactly like this."""
    result = assess("Tribes/Tribal Organizations")
    assert result["tribe_named_as_eligible_class"] == NAMED_YES
    assert result["federal_recognition"] == "NOT_STATED"
    assert result["federal_recognition_stated"] is False


def test_recognition_is_never_inferred_from_a_bare_tribe():
    """Requiring "federally recognized" returned UNKNOWN for nine of eighteen
    live records; inventing the requirement is the opposite error."""
    result = assess("Tribes")
    assert TRIBE_FEDERALLY_RECOGNIZED not in result["entity_classes"]
    assert TRIBE_RECOGNITION_UNSPECIFIED in result["entity_classes"]


def test_state_recognition_is_never_inferred():
    result = assess("Federally recognized Indian Tribes")
    assert TRIBE_STATE_RECOGNIZED not in result["entity_classes"]
    assert result["state_recognition_never_inferred"] is True


def test_state_recognition_is_recorded_when_the_publisher_states_it():
    result = assess("State-recognized Tribes are also eligible.")
    assert TRIBE_STATE_RECOGNIZED in result["entity_classes"]
    assert result["federal_recognition"] == "STATE_RECOGNITION_STATED"


def test_no_tribe_class_gives_no_recognition_answer():
    assert assess("IHS contracted UIOs")["federal_recognition"] == (
        "NO_TRIBE_CLASS_NAMED"
    )


# ---- classes are legal classes, never synonyms ------------------------


def test_a_tribal_organization_is_not_a_tribal_government():
    result = assess("Tribal Organizations only.")
    assert TRIBAL_ORGANIZATION in result["entity_classes"]
    assert result["tribal_government_classes_named"] == []


def test_an_urban_indian_organization_is_not_a_kind_of_tribe():
    result = assess("Urban Indian Organizations")
    assert URBAN_INDIAN_ORGANIZATION in result["entity_classes"]
    assert not any(c.startswith("TRIBE_") for c in result["entity_classes"])


def test_a_tribal_epidemiology_centre_keeps_its_own_class():
    result = extract_entity_classes("Tribal Epidemiology Centers")
    assert TRIBAL_EPIDEMIOLOGY_CENTER in result["entity_classes"]


def test_distinct_classes_are_all_reported_not_merged():
    result = assess(
        "Federally recognized Indian Tribes, Tribal Organizations, and Urban "
        "Indian Organizations may apply."
    )
    for expected in (
        TRIBE_FEDERALLY_RECOGNIZED,
        TRIBAL_ORGANIZATION,
        URBAN_INDIAN_ORGANIZATION,
    ):
        assert expected in result["entity_classes"]
    assert result["classes_are_legal_classes_not_synonyms"] is True


def test_evidence_is_reported_so_a_reviewer_can_check_the_reading():
    result = assess("Urban Indian Organizations")
    assert result["class_evidence"][URBAN_INDIAN_ORGANIZATION]


# ---- the plural / stem regression class -------------------------------


@pytest.mark.parametrize(
    "prose,expected",
    [
        ("Indian Tribe", TRIBE_FEDERALLY_RECOGNIZED),
        ("Indian Tribes", TRIBE_FEDERALLY_RECOGNIZED),
        ("Tribal government", TRIBE_FEDERALLY_RECOGNIZED),
        ("Tribal governments", TRIBE_FEDERALLY_RECOGNIZED),
        ("Tribe", TRIBE_RECOGNITION_UNSPECIFIED),
        ("Tribes", TRIBE_RECOGNITION_UNSPECIFIED),
        ("Tribal Organization", TRIBAL_ORGANIZATION),
        ("Tribal Organizations", TRIBAL_ORGANIZATION),
        ("Urban Indian Organization", URBAN_INDIAN_ORGANIZATION),
        ("Urban Indian Organizations", URBAN_INDIAN_ORGANIZATION),
        ("UIO", URBAN_INDIAN_ORGANIZATION),
        ("UIOs", URBAN_INDIAN_ORGANIZATION),
        ("Urban Organizations", URBAN_INDIAN_ORGANIZATION),
        ("Tribal Epidemiology Center", TRIBAL_EPIDEMIOLOGY_CENTER),
        ("Tribal Epidemiology Centers", TRIBAL_EPIDEMIOLOGY_CENTER),
    ],
)
def test_singular_and_plural_both_classify(prose, expected):
    """A closing \\b has now shipped twice and hidden real money twice.

    Statutory prose is written in both numbers, so every class is checked in
    both. This is a known regression class, not an isolated typo.
    """
    assert expected in extract_entity_classes(prose)["entity_classes"]


def test_alaska_native_villages_are_a_tribal_government_class():
    result = assess("Alaska Native villages")
    assert TRIBE_FEDERALLY_RECOGNIZED in result["entity_classes"]


# ---- falsifiability ---------------------------------------------------


def test_the_reader_can_return_no_and_does():
    """A detector that never says NO is not a detector."""
    assert (
        assess("Eligible applicants are 501(c)(3) organizations only.")[
            "tribe_named_as_eligible_class"
        ]
        == NAMED_NO
    )


def test_the_reader_can_return_unknown_and_does():
    assert assess(None)["tribe_named_as_eligible_class"] == NAMED_UNKNOWN


def test_unrelated_prose_finds_no_native_evidence():
    result = assess("Eligible applicants are county governments.")
    assert result["native_relevant_evidence_present"] is False


def test_replay_is_deterministic():
    assert assess("Tribes/Tribal Organizations") == assess(
        "Tribes/Tribal Organizations"
    )


# ---- the portfolio summary --------------------------------------------


def test_the_summary_counts_what_is_closed_to_tribes():
    assessments = [
        assess("Tribes, Tribal Organizations, Urban Organizations"),
        assess("IHS contracted UIOs"),
        assess("AIAN National organization"),
        assess("To be eligible an applicant must be a 501(c)(3) organization."),
    ]
    summary = summarize_entity_classes(assessments)
    assert summary["assessment_count"] == 4
    assert summary["by_tribe_named"][NAMED_YES] == 1
    assert summary["by_tribe_named"][NAMED_NO] == 1
    assert summary["native_serving_is_not_tribe_eligible"] is True


def test_an_empty_portfolio_summarises_to_zero():
    summary = summarize_entity_classes([])
    assert summary["assessment_count"] == 0
    assert summary["not_named_for_tribes"] == 0


# ---- genericity -------------------------------------------------------


def test_the_reader_names_no_agency():
    import ast
    import inspect

    from nativeforge.services import native_entity_class_service as svc

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
    for leak in ("ihs", "hud", "onap", "grants_gov", "indian_health"):
        assert leak not in haystack, f"publisher-specific identifier: {leak}"
