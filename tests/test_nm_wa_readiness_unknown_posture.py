"""Sprint 28: UNKNOWN grant_posture maps to incomplete readiness."""

from __future__ import annotations

from nativeforge.services.nm_wa_pilot_rollup_service import (
    READINESS_INCOMPLETE_PROFILE,
    assign_conservative_readiness_label,
)


def test_unknown_posture_incomplete() -> None:
    assert (
        assign_conservative_readiness_label(
            {"program_areas_unknown": False, "grant_posture": "UNKNOWN"}
        )
        == READINESS_INCOMPLETE_PROFILE
    )
