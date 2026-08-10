"""WA-15: matching profile selector wires WA pilot profiles."""

from __future__ import annotations

import pytest

from nativeforge.services.matching_profile_selector_service import (
    list_available_matching_profiles,
    resolve_matching_profile,
)
from nativeforge.services.wa_pilot_fixture_loader_service import fixtures_present


@pytest.mark.skipif(
    not fixtures_present()["profiles"],
    reason="WA pilot fixtures not present",
)
def test_selector_lists_and_resolves_wa_pilot() -> None:
    keys = [p["fixture_key"] for p in list_available_matching_profiles()]
    wa_keys = [k for k in keys if str(k).startswith("wa_pilot_")]
    assert len(wa_keys) >= 29
    prof = resolve_matching_profile(profile_fixture_key=wa_keys[0])
    assert prof["profile_selector"]["wa_pilot"] is True
