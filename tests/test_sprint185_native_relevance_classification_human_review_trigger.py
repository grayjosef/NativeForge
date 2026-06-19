"""Sprint 185: human-review trigger vocabulary."""

from __future__ import annotations

from nativeforge.services.native_relevance_classification_human_review_trigger_service import (
    HUMAN_REVIEW_TRIGGERS,
    SCHEMA_VERSION,
    TRIGGER_KEYWORD_HYPOTHESIS_ONLY,
    TRIGGER_OVERCLAIM_BLOCKED,
    build_human_review_trigger_contract,
    evaluate_human_review_required,
    is_valid_human_review_trigger,
)


def test_seven_human_review_triggers() -> None:
    assert len(HUMAN_REVIEW_TRIGGERS) == 7
    assert TRIGGER_OVERCLAIM_BLOCKED in HUMAN_REVIEW_TRIGGERS


def test_keyword_hypothesis_triggers_review() -> None:
    result = evaluate_human_review_required(
        trigger_codes=[TRIGGER_KEYWORD_HYPOTHESIS_ONLY],
    )
    assert result["human_review_required"] is True


def test_build_contract() -> None:
    contract = build_human_review_trigger_contract()
    assert contract["schema_version"] == SCHEMA_VERSION


def test_invalid_trigger_ignored() -> None:
    result = evaluate_human_review_required(trigger_codes=["bogus"])
    assert result["human_review_required"] is False
    assert not is_valid_human_review_trigger("bogus")
