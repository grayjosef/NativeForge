"""WA-11/12: WA pilot fixture loader — count, federal recognition, offline load."""

from __future__ import annotations

import pytest

from nativeforge.services.wa_pilot_fixture_loader_service import (
    EXPECTED_PROFILE_COUNT,
    build_wa_pilot_fixture_contract,
    fixtures_present,
    load_wa_tribal_profiles,
    require_wa_pilot_fixtures,
)


@pytest.mark.skipif(
    not fixtures_present()["profiles"],
    reason="WA pilot fixtures not present",
)
def test_wa_fixture_loads_29_federal_profiles() -> None:
    require_wa_pilot_fixtures()
    profiles = load_wa_tribal_profiles()
    assert len(profiles) == EXPECTED_PROFILE_COUNT
    assert all(p["recognition_type"] == "federal" for p in profiles)
    assert all(str(p["fixture_key"]).startswith("wa_pilot_") for p in profiles)


@pytest.mark.skipif(
    not fixtures_present()["profiles"],
    reason="WA pilot fixtures not present",
)
def test_wa_fixture_contract_ready() -> None:
    contract = build_wa_pilot_fixture_contract()
    assert contract["ready"] is True
    assert contract["profile_count"] == EXPECTED_PROFILE_COUNT
    assert contract["expected_profile_count"] == EXPECTED_PROFILE_COUNT
