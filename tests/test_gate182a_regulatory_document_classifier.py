"""Gate 182A — a government notice stream is not an opportunity pipeline.

Measured on the live Federal Register, 2026-07-01..2026-09-25: 6,295 documents,
989 matching "tribal". Of 100 of those sampled and run through this classifier:

    47  POLICY_RULEMAKING      -> early signal
    22  ADMINISTRATIVE         -> not routed
    18  OTHER                  -> not routed
    10  REPATRIATION_NOTICE    -> intelligence only
     2  FUNDING_NOTICE         -> opportunity graph
     1  CONSULTATION           -> intelligence only

98 of 100 do not become opportunities. Offline; the live measurement is
reported separately.
"""

from __future__ import annotations

import pytest

from nativeforge.services.regulatory_document_classifier_service import (
    ADMINISTRATIVE,
    CONSULTATION,
    FUNDING_NOTICE,
    OTHER,
    POLICY_RULEMAKING,
    PROGRAM_NOTICE,
    REPATRIATION_NOTICE,
    ROUTE_DISCARD,
    ROUTE_EARLY_SIGNAL,
    ROUTE_INTELLIGENCE,
    ROUTE_OPPORTUNITY,
    classify_document,
    summarize_classifications,
)

FMAP = {"title": "title", "abstract": "abstract", "doc_type": "type"}


def doc(title, *, abstract="", doc_type="Notice"):
    return {"title": title, "abstract": abstract, "type": doc_type}


def classify(title, **kw):
    return classify_document(doc(title, **kw), field_map=FMAP)


# ---- the false positives that made this necessary ---------------------


def test_an_information_collection_filing_is_not_funding():
    """Real title from the measured sample. The naive pass called it funding."""
    result = classify(
        "Agency Information Collection Activities; Submission to the Office of "
        "Management and Budget for Review; Tribal Grant Program Data"
    )
    assert result["classification"] == ADMINISTRATIVE
    assert result["route"] == ROUTE_DISCARD
    assert result["may_become_opportunity"] is False


def test_a_paperwork_reduction_notice_is_not_funding():
    result = classify(
        "Proposed Collection; Comment Request; Paperwork Reduction Act "
        "Submission for the Indian Housing Grant"
    )
    assert result["classification"] == ADMINISTRATIVE
    assert result["may_become_opportunity"] is False


def test_a_sunshine_act_meeting_is_not_an_opportunity():
    assert classify("Sunshine Act Meetings")["classification"] == ADMINISTRATIVE


# ---- what genuinely is a funding notice -------------------------------


def test_a_notice_of_funding_availability_is_a_funding_notice():
    result = classify("Notice of Funding Availability for Tribal Transportation")
    assert result["classification"] == FUNDING_NOTICE
    assert result["route"] == ROUTE_OPPORTUNITY
    assert result["may_become_opportunity"] is True


@pytest.mark.parametrize(
    "title",
    [
        "Notice of Supplemental Funding, Medicare Rural Hospital Flexibility",
        "Funding Opportunity for Native American Language Preservation",
        "Request for Applications: Tribal Climate Resilience",
        "Cooperative Agreement for Indian Health Service Facilities",
    ],
)
def test_real_funding_shapes_are_recognised(title):
    assert classify(title)["classification"] == FUNDING_NOTICE


def test_the_word_grant_alone_does_not_make_a_funding_notice():
    """'grant of authority' and 'granted' are how filings look like money."""
    result = classify("Notice of Grant of Authority to Operate a Foreign Trade Zone")
    assert result["classification"] != FUNDING_NOTICE


# ---- repatriation: Native-relevant, never an opportunity --------------


def test_a_repatriation_notice_is_native_relevant_and_not_funding():
    result = classify(
        "Notice of Intended Repatriation: University of Minnesota, Minneapolis, MN"
    )
    assert result["classification"] == REPATRIATION_NOTICE
    assert result["route"] == ROUTE_INTELLIGENCE
    assert result["may_become_opportunity"] is False


def test_an_inventory_completion_notice_is_repatriation():
    result = classify("Notice of Inventory Completion: Auburn University, AL")
    assert result["classification"] == REPATRIATION_NOTICE
    assert result["route"] != ROUTE_OPPORTUNITY


def test_repatriation_is_checked_before_funding():
    """A repatriation notice mentioning a grant is still repatriation."""
    result = classify(
        "Notice of Inventory Completion: repatriation supported by grant funds"
    )
    assert result["classification"] == REPATRIATION_NOTICE


# ---- consultation and rulemaking --------------------------------------


def test_a_consultation_notice_is_intelligence_not_an_opportunity():
    result = classify("Notice of Tribal Consultation on Water Rights")
    assert result["classification"] == CONSULTATION
    assert result["route"] == ROUTE_INTELLIGENCE
    assert result["may_become_opportunity"] is False


def test_a_rule_is_policy_rulemaking_and_an_early_signal():
    result = classify("Indian Health Service Payment Rates", doc_type="Rule")
    assert result["classification"] == POLICY_RULEMAKING
    assert result["route"] == ROUTE_EARLY_SIGNAL
    assert result["may_become_opportunity"] is False


def test_a_proposed_rule_is_also_rulemaking():
    result = classify("Tribal Water Standards", doc_type="Proposed Rule")
    assert result["classification"] == POLICY_RULEMAKING


def test_a_program_notice_implies_no_application():
    result = classify("Annual Notice of Program Description for Tribal Colleges")
    assert result["classification"] == PROGRAM_NOTICE
    assert result["may_become_opportunity"] is False


def test_an_unclassifiable_document_is_other_not_a_guess():
    result = classify("Agency Forms Undergoing Review")
    assert result["classification"] == OTHER
    assert result["route"] == ROUTE_DISCARD
    assert "no_classifying_signal_found" in result["reasons"]


# ---- Native evidence is a SEPARATE question ---------------------------


def test_funding_without_native_evidence_is_still_funding():
    """Both real funding notices in the measured sample looked like this."""
    result = classify("Notice of Funding Availability for State Highway Safety")
    assert result["classification"] == FUNDING_NOTICE
    assert result["has_native_evidence"] is False
    assert result["native_evidence_terms"] == []


def test_native_evidence_without_funding_is_still_native():
    result = classify("Notice of Inventory Completion: Tribal human remains")
    assert result["has_native_evidence"] is True
    assert result["may_become_opportunity"] is False


def test_the_classifier_decides_neither_relevance_nor_eligibility():
    result = classify("Funding Opportunity for Tribal Governments")
    assert result["native_relevance_decided"] is False
    assert result["native_relevance_is_decided_by_gate_173"] is True
    assert result["eligibility_decided"] is False
    assert "relevance_class" not in result


def test_a_place_name_is_not_native_evidence():
    """Wave 1D's guard, carried forward."""
    result = classify("Notice of Funding Availability for Rural Alaska Utilities")
    assert "alaska native" not in result["native_evidence_terms"]
    assert result["has_native_evidence"] is False


# ---- routing invariants ----------------------------------------------


def test_only_funding_notices_may_reach_the_opportunity_graph():
    for title, kw in (
        ("Notice of Tribal Consultation", {}),
        ("Notice of Inventory Completion", {}),
        ("Sunshine Act Meetings", {}),
        ("Tribal Water Standards", {"doc_type": "Rule"}),
        ("Agency Forms Undergoing Review", {}),
    ):
        result = classify(title, **kw)
        assert result["route"] != ROUTE_OPPORTUNITY, title
        assert result["may_become_opportunity"] is False, title


def test_every_document_carries_the_refusal():
    assert classify("anything at all")["a_notice_is_not_an_opportunity"] is True


# ---- the summary that stops a stream reading as a pipeline ------------


def test_the_summary_separates_documents_from_opportunities():
    classifications = (
        [classify("Tribal Water Standards", doc_type="Rule")] * 47
        + [classify("Sunshine Act Meetings")] * 22
        + [classify("Agency Forms Undergoing Review")] * 18
        + [classify("Notice of Inventory Completion: Auburn")] * 10
        + [classify("Notice of Funding Availability for Tribes")] * 2
        + [classify("Notice of Tribal Consultation")] * 1
    )
    summary = summarize_classifications(classifications)

    assert summary["document_count"] == 100
    assert summary["opportunity_eligible_count"] == 2
    assert summary["documents_not_becoming_opportunities"] == 98
    assert summary["by_route"][ROUTE_EARLY_SIGNAL] == 47
    assert summary["by_route"][ROUTE_OPPORTUNITY] == 2
    assert summary["document_count_is_not_opportunity_count"] is True


def test_replay_is_deterministic():
    assert classify("Notice of Funding Availability") == classify(
        "Notice of Funding Availability"
    )


# ---- genericity -------------------------------------------------------


def test_the_classifier_names_no_publisher():
    import ast
    import inspect

    from nativeforge.services import regulatory_document_classifier_service as svc

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
    for leak in ("federal_register", "federalregister", "grants_gov", "denali"):
        assert leak not in haystack, f"publisher-specific identifier: {leak}"


def test_another_registers_field_names_work_unchanged():
    other = {"heading": "Notice of Funding Availability", "kind": "Bulletin"}
    result = classify_document(
        other, field_map={"title": "heading", "doc_type": "kind"}
    )
    assert result["classification"] == FUNDING_NOTICE
