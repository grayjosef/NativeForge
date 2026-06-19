"""Sprint 199: blockers and missing data."""

from __future__ import annotations

from nativeforge.services.eligibility_fit_assessment_blockers_service import (
    BLOCKER_MISSING_PROFILE,
    build_blockers_assessment,
)
from nativeforge.services.eligibility_fit_assessment_missing_data_service import (
    FLAG_MISSING_APPLICANT_TYPE,
    build_missing_data_assessment,
)


def test_blockers_assessment() -> None:
    result = build_blockers_assessment(blocker_codes=[BLOCKER_MISSING_PROFILE])
    assert result["application_blocked"] is True
    assert BLOCKER_MISSING_PROFILE in result["blocker_codes"]


def test_missing_data_assessment() -> None:
    result = build_missing_data_assessment(flags=[FLAG_MISSING_APPLICANT_TYPE])
    assert result["data_incomplete"] is True
