"""Gate 182F — certification is not identity, and zero is not failure.

Measured live on a Native-designated federal fund, 2026-09-25.

Its complete corpus is 63 records, pulled uncapped, and EVERY ONE is archived.
A negative control agency code returns 0, so the zero is real: the programme
posts every year from 2007 to 2026 and simply has nothing open today. A
collector that reports that as breakage trains operators to ignore it; one
that reports it as coverage lies.

Its eligibility gate is not an entity class at all:

    "Certified CDFIs, Emerging CDFIs, and Sponsoring Entities (organizations
     primarily serving Native Communities that propose to create a separate
     Certified CDFI) are eligible to apply"

Three certification states, no statutory Native entity class among them. A
Tribe reading "Native-designated capital" would assume it qualifies; the
actual gate is a certification it may not hold.

Offline.
"""

from __future__ import annotations

import pytest

from nativeforge.services.native_entity_class_service import (
    CERTIFICATION_EMERGING,
    CERTIFICATION_HELD,
    CERTIFICATION_NOT_MENTIONED,
    CERTIFICATION_SPONSOR,
    NAMED_UNKNOWN,
    NAMED_YES,
    TRIBE_FEDERALLY_RECOGNIZED,
    assess_certification_requirement,
    assess_tribal_applicant_class,
)

REAL_CDFI_PROSE = (
    "Certified CDFIs, Emerging CDFIs, and Sponsoring Entities (organizations "
    "primarily serving Native Communities that propose to create a separate "
    "Certified CDFI) are eligible to apply for Technical Assistance."
)


def cert(prose):
    return assess_certification_requirement(prose)


# ---- certification is its own axis ------------------------------------


def test_the_real_prose_yields_three_certification_states():
    result = cert(REAL_CDFI_PROSE)
    assert CERTIFICATION_HELD in result["certification_states"]
    assert CERTIFICATION_EMERGING in result["certification_states"]
    assert CERTIFICATION_SPONSOR in result["certification_states"]
    assert result["certification_gate_present"] is True


def test_certification_is_not_reported_as_an_entity_class():
    """The entity reader returning nothing here is correct, and incomplete.
    The certification axis is the missing half, not a replacement."""
    entity = assess_tribal_applicant_class(REAL_CDFI_PROSE)
    assert entity["entity_classes"] == []
    assert cert(REAL_CDFI_PROSE)["certification_is_not_an_entity_class"] is True


def test_a_native_designated_fund_does_not_make_a_tribe_eligible():
    """The programme serves Native communities. That is not the gate."""
    entity = assess_tribal_applicant_class(
        REAL_CDFI_PROSE, publisher_is_native_serving=True
    )
    assert entity["tribe_named_as_eligible_class"] == NAMED_UNKNOWN
    assert cert(REAL_CDFI_PROSE)["certification_is_not_native_identity"] is True


def test_an_entity_gated_programme_has_no_certification_gate():
    """The two axes are orthogonal, and the control proves it."""
    prose = "Federally recognized Indian Tribes are eligible."
    assert cert(prose)["certification_gate_present"] is False
    assert cert(prose)["certification_state"] == CERTIFICATION_NOT_MENTIONED
    entity = assess_tribal_applicant_class(prose)
    assert TRIBE_FEDERALLY_RECOGNIZED in entity["entity_classes"]
    assert entity["tribe_named_as_eligible_class"] == NAMED_YES


def test_holding_the_certification_is_a_tenant_fact_gate_174_owns():
    result = cert(REAL_CDFI_PROSE)
    assert result["tenant_certification_verified"] is False
    assert result["tenant_eligibility_decided"] is False


def test_evidence_is_reported_for_review():
    assert cert(REAL_CDFI_PROSE)["certification_evidence"]


# ---- the generic forms ------------------------------------------------


@pytest.mark.parametrize(
    "phrase",
    [
        "Certified institutions may apply",
        "applicants must be certified",
        "accredited organizations",
        "licensed lenders",
        "formally designated entities",
    ],
)
def test_certification_language_is_recognised_generically(phrase):
    """Certification, accreditation, licensure and designation are one gate
    wearing different words."""
    assert cert(phrase)["certification_gate_present"] is True


@pytest.mark.parametrize(
    "phrase",
    [
        "Emerging CDFIs",
        "must certify within three years",
        "organizations not yet certified",
    ],
)
def test_the_emerging_path_is_distinguished_from_holding_it(phrase):
    assert CERTIFICATION_EMERGING in cert(phrase)["certification_states"]


@pytest.mark.parametrize(
    "phrase", ["Sponsoring Entity", "Sponsoring Entities", "sponsor organization"]
)
def test_sponsor_matches_singular_and_plural(phrase):
    """Entity/Entities shares no stem ending, so both are spelled out."""
    assert CERTIFICATION_SPONSOR in cert(phrase)["certification_states"]


def test_an_emerging_applicant_is_not_a_certified_one():
    result = cert("Emerging CDFIs may apply.")
    assert CERTIFICATION_EMERGING in result["certification_states"]
    assert CERTIFICATION_HELD not in result["certification_states"]


# ---- honest silence ---------------------------------------------------


@pytest.mark.parametrize("empty", [None, "", "   "])
def test_absent_prose_reports_no_gate_rather_than_guessing(empty):
    result = cert(empty)
    assert result["certification_gate_present"] is False
    assert result["certification_states"] == []


def test_unrelated_prose_finds_no_certification():
    assert (
        cert("This programme supports rural water systems.")[
            "certification_gate_present"
        ]
        is False
    )


def test_replay_is_deterministic():
    assert cert(REAL_CDFI_PROSE) == cert(REAL_CDFI_PROSE)


# ---- genericity -------------------------------------------------------


def test_the_certification_axis_names_no_publisher():
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
        elif isinstance(node, ast.FunctionDef):
            names.append(node.name)
    haystack = " ".join(names).lower()
    for leak in ("cdfi", "naca", "treasury", "ihs", "hud", "epa"):
        assert leak not in haystack, f"publisher-specific identifier: {leak}"
