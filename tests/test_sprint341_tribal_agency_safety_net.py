"""Sprint 341: tribal-serving agency safety net tests."""

from __future__ import annotations

from nativeforge.services.native_relevance_classification_evaluator_service import (
    classify_native_relevance,
)
from nativeforge.services.tribal_serving_agency_safety_net_service import (
    apply_tribal_agency_safety_net,
    is_tribal_serving_agency,
)


def test_tribal_agency_patterns() -> None:
    assert is_tribal_serving_agency(agency="BIA / Interior")
    assert is_tribal_serving_agency(agency="SAMHSA / HHS", opportunity_title="AI/AN grant")
    assert not is_tribal_serving_agency(agency="National Science Foundation")


def test_tribal_agency_empty_evidence_routes_to_review() -> None:
    net = apply_tribal_agency_safety_net(
        grant={
            "agency": "SAMHSA / HHS",
            "opportunity_title": "AI/AN Zero Suicide",
            "eligibility_text": "Open to eligible applicants per program guidelines.",
        },
        insufficient_evidence=True,
        proposed_label="irrelevant",
    )
    assert net["safety_net_triggered"] is True
    assert net["route_to_review"] is True


def test_tribal_agency_classified_not_irrelevant_on_placeholder() -> None:
    raw = {
        "fixture_key": "nf15-samhsa-placeholder",
        "opportunity_title": "AI/AN Zero Suicide & Suicide Prevention",
        "agency": "SAMHSA / HHS",
        "eligibility_text": "Open to eligible applicants per program guidelines.",
        "tribal_eligible": False,
        "applicant_types_include_tribal": False,
        "explicit_source_evidence": [],
    }
    result = classify_native_relevance(raw)
    assert result["classification_label"] != "irrelevant"
    assert result["human_review_required"] is True
