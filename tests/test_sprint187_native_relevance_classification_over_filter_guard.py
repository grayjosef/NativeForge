"""Sprint 187: over-filter guard invariant tests."""

from __future__ import annotations

from nativeforge.services.native_relevance_classification_label_vocabulary_service import (
    LABEL_BROADLY_ELIGIBLE_POTENTIALLY_RELEVANT,
    LABEL_IRRELEVANT,
)
from nativeforge.services.native_relevance_classification_over_filter_guard_service import (
    SCHEMA_VERSION,
    apply_over_filter_guard,
    build_over_filter_guard_contract,
    label_must_remain_discoverable,
)


def test_broad_label_cannot_be_hidden() -> None:
    result = apply_over_filter_guard(
        classification_label=LABEL_BROADLY_ELIGIBLE_POTENTIALLY_RELEVANT,
        proposed_discoverable=False,
    )
    assert result["over_filter_blocked"] is True
    assert result["final_discoverable"] is True


def test_irrelevant_may_be_non_discoverable() -> None:
    result = apply_over_filter_guard(
        classification_label=LABEL_IRRELEVANT,
        proposed_discoverable=False,
    )
    assert result["over_filter_blocked"] is False
    assert result["final_discoverable"] is False


def test_broad_label_already_discoverable_passes() -> None:
    result = apply_over_filter_guard(
        classification_label=LABEL_BROADLY_ELIGIBLE_POTENTIALLY_RELEVANT,
        proposed_discoverable=True,
    )
    assert result["over_filter_blocked"] is False


def test_label_must_remain_discoverable() -> None:
    assert label_must_remain_discoverable(LABEL_BROADLY_ELIGIBLE_POTENTIALLY_RELEVANT)
    assert not label_must_remain_discoverable(LABEL_IRRELEVANT)


def test_build_contract() -> None:
    contract = build_over_filter_guard_contract()
    assert contract["schema_version"] == SCHEMA_VERSION
