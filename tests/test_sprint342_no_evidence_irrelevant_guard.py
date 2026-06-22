"""Sprint 342: no-evidence irrelevant guard tests."""

from __future__ import annotations

import pytest

from nativeforge.services.native_relevance_classification_evaluator_service import (
    classify_native_relevance,
)
from nativeforge.services.no_evidence_irrelevant_guard_service import (
    NoEvidenceIrrelevantError,
    apply_no_evidence_irrelevant_guard,
    assert_no_evidence_not_irrelevant,
)


def test_empty_evidence_never_irrelevant() -> None:
    grant = {
        "grant_id": "nf15-test-empty",
        "opportunity_title": "Community services grant",
        "eligibility_text": "",
        "tribal_eligible": False,
        "applicant_types_include_tribal": False,
    }
    result = apply_no_evidence_irrelevant_guard(
        proposed_label="irrelevant",
        grant=grant,
    )
    assert result["final_label"] == "uncertain_relevance"
    assert result["no_evidence_blocked"] is True
    assert result["eligibility_evidence_status"] == "insufficient_data"


def test_placeholder_evidence_never_irrelevant() -> None:
    grant = {
        "grant_id": "nf15-test-placeholder",
        "opportunity_title": "AI/AN Zero Suicide",
        "agency": "SAMHSA / HHS",
        "eligibility_text": "Open to eligible applicants per program guidelines.",
        "tribal_eligible": False,
        "applicant_types_include_tribal": False,
    }
    raw = {
        **grant,
        "explicit_source_evidence": [],
    }
    classified = classify_native_relevance(raw)
    assert classified["classification_label"] != "irrelevant"
    assert classified["eligibility_evidence_status"] == "insufficient_data"


def test_assert_fails_on_insufficient_irrelevant() -> None:
    with pytest.raises(NoEvidenceIrrelevantError):
        assert_no_evidence_not_irrelevant(
            grant_id="bad",
            classification_label="irrelevant",
            eligibility_evidence_status="insufficient_data",
        )


def test_positive_small_business_only_may_be_irrelevant() -> None:
    grant = {
        "grant_id": "nf15-test-sbir",
        "opportunity_title": "NSF SBIR Phase I",
        "eligibility_text": (
            "Applicant types: Small businesses\n\n"
            "Only United States small business concerns (SBCs) may apply."
        ),
        "tribal_eligible": False,
        "applicant_types_include_tribal": False,
        "explicit_source_evidence": [],
    }
    classified = classify_native_relevance(grant)
    assert classified["classification_label"] == "irrelevant"
