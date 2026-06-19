"""Sprint 221: matching evaluator."""

from __future__ import annotations

from nativeforge.services.matching_readiness_demo_fixture_service import (
    load_matching_readiness_demo_pairs,
    resolve_demo_pair,
)
from nativeforge.services.matching_readiness_match_label_vocabulary_service import (
    LABEL_BLOCKED,
    LABEL_NEEDS_OPERATOR_REVIEW,
    LABEL_NOT_FIT,
    LABEL_STRONG_FIT,
)
from nativeforge.services.matching_readiness_matching_evaluator_service import (
    SCHEMA_VERSION,
    evaluate_match,
)


def test_strong_fit_with_confirmation() -> None:
    pair = next(p for p in load_matching_readiness_demo_pairs() if p["fixture_key"] == "mr_demo_strong_fit")
    opp, profile = resolve_demo_pair(pair)
    result = evaluate_match(opp, profile, pair_meta=pair)
    assert result["schema_version"] == SCHEMA_VERSION
    assert result["match_label"] == LABEL_STRONG_FIT


def test_unconfirmed_strong_fit_needs_operator_review() -> None:
    pair = next(
        p for p in load_matching_readiness_demo_pairs() if p["fixture_key"] == "mr_demo_strong_unconfirmed"
    )
    opp, profile = resolve_demo_pair(pair)
    result = evaluate_match(opp, profile, pair_meta=pair)
    assert result["match_label"] == LABEL_NEEDS_OPERATOR_REVIEW


def test_missing_profile_needs_more_data() -> None:
    pair = next(
        p for p in load_matching_readiness_demo_pairs() if p["fixture_key"] == "mr_demo_incomplete_profile"
    )
    opp, profile = resolve_demo_pair(pair)
    result = evaluate_match(opp, profile, pair_meta=pair)
    assert result["missing_data_guard"]["fail_closed_triggered"] is True


def test_geography_mismatch_blocked_or_not_fit() -> None:
    pair = next(
        p for p in load_matching_readiness_demo_pairs() if p["fixture_key"] == "mr_demo_geography_blocked"
    )
    opp, profile = resolve_demo_pair(pair)
    result = evaluate_match(opp, profile, pair_meta=pair)
    assert result["match_label"] in {LABEL_BLOCKED, LABEL_NEEDS_OPERATOR_REVIEW, LABEL_NOT_FIT}
