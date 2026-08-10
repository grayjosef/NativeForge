"""Sprint 009: inspect existing NM/WA fixtures offline for report foundation."""

from __future__ import annotations

from nativeforge.services.nm_pilot_fixture_loader_service import (
    EXPECTED_PROFILE_COUNT as NM_N,
    load_nm_tribal_profiles,
)
from nativeforge.services.wa_pilot_fixture_loader_service import (
    EXPECTED_PROFILE_COUNT as WA_N,
    load_wa_tribal_profiles,
)


def test_nm_wa_fixtures_load_offline() -> None:
    nm = load_nm_tribal_profiles()
    wa = load_wa_tribal_profiles()
    assert len(nm) == NM_N == 22
    assert len(wa) == WA_N == 29
    assert all(p["recognition_type"] == "federal" for p in nm + wa)
