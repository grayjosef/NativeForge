"""Sprint 335: tribe-eligible broad discoverability guard — must fail on over-filter."""

from __future__ import annotations

import pytest

from nativeforge.services.tribe_eligible_broad_discoverability_guard_service import (
    TribeEligibleBroadFilteredError,
    apply_tribe_eligible_broad_discoverability_guard,
    assert_tribe_eligible_broad_discoverable,
)


def test_tribe_eligible_broad_irrelevant_raises() -> None:
    with pytest.raises(TribeEligibleBroadFilteredError):
        assert_tribe_eligible_broad_discoverable(
            grant_id="nf14-test-broad",
            tribe_eligible_broad=True,
            classification_label="irrelevant",
            discoverable=False,
        )


def test_tribe_eligible_broad_discoverable_passes() -> None:
    assert_tribe_eligible_broad_discoverable(
        grant_id="nf14-test-edge",
        tribe_eligible_broad=True,
        classification_label="uncertain_relevance",
        discoverable=True,
    )


def test_guard_catches_over_filter() -> None:
    result = apply_tribe_eligible_broad_discoverability_guard(
        grant_id="nf14-test",
        tribe_eligible_broad=True,
        classification_label="irrelevant",
        discoverable=False,
    )
    assert result["over_filter_caught"] is True


def test_non_tribe_broad_skips_guard() -> None:
    result = apply_tribe_eligible_broad_discoverability_guard(
        grant_id="nf14-test-sbir",
        tribe_eligible_broad=False,
        classification_label="irrelevant",
        discoverable=False,
    )
    assert result["over_filter_caught"] is False
