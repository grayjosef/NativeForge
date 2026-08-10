"""Sprint 21: NM/WA shared rollup skeleton contract."""

from __future__ import annotations

from nativeforge.services.nm_wa_pilot_rollup_service import (
    build_nm_wa_pilot_rollup_skeleton,
)


def test_rollup_skeleton_offline_contract() -> None:
    sk = build_nm_wa_pilot_rollup_skeleton()
    assert sk["offline_only"] is True
    assert sk["live_ingestion"] is False
    assert sk["source_activation"] is False
    assert sk["fixtures"]["NM"]["expected_profile_count"] == 22
    assert sk["fixtures"]["WA"]["expected_profile_count"] == 29
