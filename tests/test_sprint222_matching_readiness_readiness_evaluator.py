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
    READINESS_LABELS,
    READINESS_NOT_READY_ELIGIBILITY_UNCERTAIN,
    READINESS_NOT_READY_MISSING_DOCUMENTS,
    READINESS_READY_WITH_REVIEW,
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


# Labels that let a pursuit proceed. Everything else must hold it.
PROCEED_LABELS = frozenset({READINESS_APPLICATION_READY, READINESS_READY_WITH_REVIEW})


def test_incomplete_profile_blocked_readiness() -> None:
    """An incomplete profile is held, and the reason is named.

    Was asserting the label was `blocked` or `not_ready_eligibility_uncertain`.
    The evaluator later gained `not_ready_missing_documents`, which is a *more*
    precise answer for this fixture - the profile is missing documents, not of
    uncertain eligibility. The assertion is tightened to the exact label rather
    than loosened to "any not_ready".
    """
    pair = next(
        p for p in load_matching_readiness_demo_pairs() if p["fixture_key"] == "mr_demo_incomplete_profile"
    )
    opp, profile = resolve_demo_pair(pair)
    result = evaluate_readiness(opp, profile, pair_meta=pair)

    label = result["readiness_label"]
    assert label == READINESS_NOT_READY_MISSING_DOCUMENTS
    # Whatever the label, an incomplete profile must never be allowed to proceed.
    assert label in READINESS_LABELS
    assert label not in PROCEED_LABELS
    assert result["final_eligibility"] is False


def test_added_readiness_labels_cannot_bypass_blocking() -> None:
    """A label added to the vocabulary must not silently become a proceed label.

    This is what let the previous assertion rot unnoticed: the vocabulary grew
    and nothing checked what the new members were allowed to mean.
    """
    assert PROCEED_LABELS <= set(READINESS_LABELS)
    for held in (
        READINESS_BLOCKED,
        READINESS_NOT_READY_ELIGIBILITY_UNCERTAIN,
        READINESS_NOT_READY_MISSING_DOCUMENTS,
    ):
        assert held in READINESS_LABELS
        assert held not in PROCEED_LABELS
