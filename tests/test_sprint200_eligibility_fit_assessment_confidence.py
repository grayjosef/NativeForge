"""Sprint 200: fit confidence and human-review status."""

from __future__ import annotations

from nativeforge.services.eligibility_fit_assessment_confidence_service import (
    CONFIDENCE_HIGH,
    CONFIDENCE_UNKNOWN,
    REVIEW_BLOCKED_PENDING_EVIDENCE,
    REVIEW_REQUIRED,
    SCHEMA_VERSION,
    build_fit_confidence_contract,
    merge_fit_confidence_levels,
    resolve_human_review_status,
)


def test_merge_picks_highest_confidence() -> None:
    merged = merge_fit_confidence_levels(["low", "high"])
    assert merged == CONFIDENCE_HIGH


def test_human_review_blocked_when_pending_evidence() -> None:
    status = resolve_human_review_status(
        human_review_required=True,
        blocked_pending_evidence=True,
    )
    assert status == REVIEW_BLOCKED_PENDING_EVIDENCE


def test_human_review_required() -> None:
    status = resolve_human_review_status(
        human_review_required=True,
        blocked_pending_evidence=False,
    )
    assert status == REVIEW_REQUIRED


def test_build_contract() -> None:
    contract = build_fit_confidence_contract()
    assert contract["schema_version"] == SCHEMA_VERSION
    assert CONFIDENCE_UNKNOWN in contract["fit_confidence_levels"]
