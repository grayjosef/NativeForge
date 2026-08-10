"""NM-03/04: NM pilot profile loader — public_inferred, no evidence codes."""

from __future__ import annotations

import pytest

from nativeforge.services.matching_profile_provenance_service import (
    CAPTURE_PUBLIC_INFERRED,
)
from nativeforge.services.nm_pilot_fixture_loader_service import (
    EXPECTED_PROFILE_COUNT,
    fixtures_present,
)
from nativeforge.services.nm_pilot_profile_loader_service import (
    list_nm_pilot_profiles,
    resolve_nm_pilot_profile,
)


@pytest.mark.skipif(
    not fixtures_present()["profiles"],
    reason="NM pilot fixtures not present",
)
def test_nm_profiles_public_inferred_no_evidence_codes() -> None:
    profiles = list_nm_pilot_profiles(require_files=True)
    assert len(profiles) == EXPECTED_PROFILE_COUNT
    for p in profiles:
        prof = resolve_nm_pilot_profile(p["fixture_key"])
        assert prof["capture_method"] == CAPTURE_PUBLIC_INFERRED
        assert prof["profile_evidence_codes"] == []
        assert prof["recognition_type"] == "federal"
        assert prof["profile_selector"]["nm_pilot"] is True
