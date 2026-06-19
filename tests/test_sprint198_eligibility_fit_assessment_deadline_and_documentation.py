"""Sprint 198: deadline risk and documentation readiness."""

from __future__ import annotations

from nativeforge.services.eligibility_fit_assessment_deadline_risk_service import (
    RISK_HIGH,
    RISK_LOW,
    assess_deadline_risk,
)
from nativeforge.services.eligibility_fit_assessment_documentation_readiness_service import (
    READINESS_COMPLETE,
    READINESS_UNKNOWN,
    assess_documentation_readiness,
)


def test_deadline_risk_high_when_close() -> None:
    result = assess_deadline_risk({"application_deadline": "2026-06-01T00:00:00Z"})
    assert result["deadline_risk"] == RISK_HIGH


def test_deadline_risk_low_when_far() -> None:
    result = assess_deadline_risk({"application_deadline": "2027-12-31T00:00:00Z"})
    assert result["deadline_risk"] == RISK_LOW


def test_deadline_missing_is_unknown() -> None:
    result = assess_deadline_risk({})
    assert result["deadline_risk"] == "unknown"
    assert result["human_review_recommended"] is True


def test_documentation_complete() -> None:
    profile = {
        "documentation_inventory": {
            "organizational_profile_complete": True,
            "tribal_resolution_on_file": True,
            "financial_statements_on_file": True,
            "authorized_signer_confirmed": True,
        }
    }
    result = assess_documentation_readiness(profile)
    assert result["documentation_readiness"] == READINESS_COMPLETE


def test_documentation_unknown_when_missing_inventory() -> None:
    result = assess_documentation_readiness({})
    assert result["documentation_readiness"] == READINESS_UNKNOWN
