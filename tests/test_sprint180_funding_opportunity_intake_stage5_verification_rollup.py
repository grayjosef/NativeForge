"""Sprint 180: Stage 5 verification rollup."""

from __future__ import annotations

from nativeforge.services.funding_opportunity_intake_stage5_verification_rollup_service import (
    SCHEMA_VERSION,
    build_stage5_verification_rollup,
)


def test_stage5_rollup_lists_components() -> None:
    out = build_stage5_verification_rollup()
    assert out["schema_version"] == SCHEMA_VERSION
    assert len(out["components"]) >= 13
