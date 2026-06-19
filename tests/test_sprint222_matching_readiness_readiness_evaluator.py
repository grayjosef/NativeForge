"""Sprint 222: readiness evaluator."""

from __future__ import annotations

from nativeforge.services.matching_readiness_demo_fixture_service import (
    load_matching_readiness_demo_pairs,
    resolve_demo_pair,
)
from nativeforge.services.matching_readiness_readiness_evaluator_service import (
    SCHEMA_VERSION,
    evaluate_readiness,
)
from nativeforge.services.matching_readiness_readiness_label_vocabulary_service import (
    READINESS_APPLICATION_READY,
    READINESS_BLOCKED,
    READINESS_NOT_READY_ELIGIBILITY_UNCERTAIN,
)


def test_strong_confirmed_pair_application_ready() -> None:
    pair = next(p for p in load_matching_readiness_demo_pairs() if p["fixture_key"] == "mr_demo_strong_fit")
    opp, profile = resolve_demo_pair(pair)
    result = evaluate_readiness(opp, profile, pair_meta=pair)
    assert result["schema_version"] == SCHEMA_VERSION
    assert result["readiness_label"] == READINESS_APPLICATION_READY


def test_unconfirmed_eligibility_blocked() -> None:
    pair = next(
        p for p in load_matching_readiness_demo_pairs() if p["fixture_key"] == "mr_demo_strong_unconfirmed"
    )
    opp, profile = resolve_demo_pair(pair)
    result = evaluate_readiness(opp, profile, pair_meta=pair)
    assert result["eligibility_guard"]["eligibility_blocked"] is True
    assert result["final_eligibility"] is False


def test_incomplete_profile_blocked_readiness() -> None:
    pair = next(
        p for p in load_matching_readiness_demo_pairs() if p["fixture_key"] == "mr_demo_incomplete_profile"
    )
    opp, profile = resolve_demo_pair(pair)
    result = evaluate_readiness(opp, profile, pair_meta=pair)
    assert result["readiness_label"] in {READINESS_BLOCKED, READINESS_NOT_READY_ELIGIBILITY_UNCERTAIN}
