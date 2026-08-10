"""NM-01/02: NM pilot fixture loader — count, federal recognition, offline load."""

from __future__ import annotations

import pytest

from nativeforge.services.nm_pilot_fixture_loader_service import (
    EXPECTED_PROFILE_COUNT,
    build_nm_pilot_fixture_contract,
    fixtures_present,
    load_nm_tribal_profiles,
    require_nm_pilot_fixtures,
)


@pytest.mark.skipif(
    not fixtures_present()["profiles"],
    reason="NM pilot fixtures not present",
)
def test_nm_fixture_loads_22_federal_profiles() -> None:
    require_nm_pilot_fixtures()
    profiles = load_nm_tribal_profiles()
    assert len(profiles) == EXPECTED_PROFILE_COUNT
    assert all(p["recognition_type"] == "federal" for p in profiles)
    assert all(str(p["fixture_key"]).startswith("nm_pilot_") for p in profiles)


@pytest.mark.skipif(
    not fixtures_present()["profiles"],
    reason="NM pilot fixtures not present",
)
def test_nm_fixture_contract_ready() -> None:
    contract = build_nm_pilot_fixture_contract()
    assert contract["ready"] is True
    assert contract["profile_count"] == EXPECTED_PROFILE_COUNT
    assert contract["expected_profile_count"] == EXPECTED_PROFILE_COUNT
