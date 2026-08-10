"""NM-05: matching profile selector wires NM pilot profiles."""

from __future__ import annotations

import pytest

from nativeforge.services.matching_profile_selector_service import (
    list_available_matching_profiles,
    resolve_matching_profile,
)
from nativeforge.services.nm_pilot_fixture_loader_service import fixtures_present


@pytest.mark.skipif(
    not fixtures_present()["profiles"],
    reason="NM pilot fixtures not present",
)
def test_selector_lists_and_resolves_nm_pilot() -> None:
    keys = [p["fixture_key"] for p in list_available_matching_profiles()]
    nm_keys = [k for k in keys if str(k).startswith("nm_pilot_")]
    assert len(nm_keys) >= 22
    prof = resolve_matching_profile(profile_fixture_key=nm_keys[0])
    assert prof["profile_selector"]["nm_pilot"] is True
