"""Sprint 186: overclaim guard invariant tests."""

from __future__ import annotations

from nativeforge.services.native_relevance_classification_label_vocabulary_service import (
    LABEL_NATIVE_ENTITY_ELIGIBLE_BROAD,
    LABEL_NATIVE_SPECIFIC,
    LABEL_WEAK_NATIVE_RELEVANCE,
)
from nativeforge.services.native_relevance_classification_overclaim_guard_service import (
    SCHEMA_VERSION,
    apply_overclaim_guard,
    build_overclaim_guard_contract,
    has_explicit_source_evidence,
)


def test_native_specific_without_evidence_is_blocked() -> None:
    result = apply_overclaim_guard(
        proposed_label=LABEL_NATIVE_SPECIFIC,
        evidence_codes=[],
        fallback_label=LABEL_WEAK_NATIVE_RELEVANCE,
    )
    assert result["overclaim_blocked"] is True
    assert result["final_label"] != LABEL_NATIVE_SPECIFIC
    assert "overclaim_blocked" in result["human_review_trigger_codes"]


def test_native_specific_with_explicit_evidence_allowed() -> None:
    result = apply_overclaim_guard(
        proposed_label=LABEL_NATIVE_SPECIFIC,
        evidence_codes=["tribal_set_aside_in_source"],
    )
    assert result["overclaim_blocked"] is False
    assert result["final_label"] == LABEL_NATIVE_SPECIFIC


def test_non_native_specific_labels_pass_through() -> None:
    result = apply_overclaim_guard(
        proposed_label=LABEL_NATIVE_ENTITY_ELIGIBLE_BROAD,
        evidence_codes=[],
    )
    assert result["final_label"] == LABEL_NATIVE_ENTITY_ELIGIBLE_BROAD
    assert result["overclaim_blocked"] is False


def test_has_explicit_source_evidence() -> None:
    assert has_explicit_source_evidence(["tribal_eligible_in_source"])
    assert not has_explicit_source_evidence(["keyword_title_hint"])


def test_build_contract() -> None:
    contract = build_overclaim_guard_contract()
    assert contract["schema_version"] == SCHEMA_VERSION
    assert contract["protected_label"] == LABEL_NATIVE_SPECIFIC
