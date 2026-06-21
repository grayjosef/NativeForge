"""Sprint 313: real_fetch honest labeling invariant guard."""

from __future__ import annotations

import pytest

from nativeforge.services.grants_gov_search_api_adapter_service import (
    load_recorded_grants_gov_search_fixture,
)
from nativeforge.services.real_fetch_honest_labeling_guard_service import (
    assert_real_fetch_honest_labeling,
)


def test_fixture_payload_never_real_fetch() -> None:
    rows = load_recorded_grants_gov_search_fixture()
    assert len(rows) >= 1
    for row in rows:
        assert row["fixture"] is True
        assert row["real_fetch"] is False
        assert_real_fetch_honest_labeling(row)


def test_invariant_fails_when_fixture_carries_real_fetch() -> None:
    with pytest.raises(ValueError, match="fixture payload cannot have real_fetch"):
        assert_real_fetch_honest_labeling(
            {
                "fetch_mode": "fixture",
                "fixture": True,
                "real_fetch": True,
                "search_live": False,
                "detail_live": False,
            }
        )


def test_invariant_fails_when_live_real_fetch_without_http_success() -> None:
    with pytest.raises(ValueError, match="requires search_live and detail_live"):
        assert_real_fetch_honest_labeling(
            {
                "fetch_mode": "live",
                "fixture": False,
                "real_fetch": True,
                "search_live": True,
                "detail_live": False,
            }
        )


def test_live_real_fetch_allowed_only_with_both_http_success() -> None:
    assert_real_fetch_honest_labeling(
        {
            "fetch_mode": "live",
            "fixture": False,
            "real_fetch": True,
            "search_live": True,
            "detail_live": True,
        }
    )
