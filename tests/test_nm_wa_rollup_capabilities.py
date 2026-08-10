"""Sprint 27: rollup skeleton advertises enabled capabilities."""

from __future__ import annotations

from nativeforge.services.nm_wa_pilot_rollup_service import (
    build_nm_wa_pilot_rollup_skeleton,
)


def test_rollup_capabilities_enabled() -> None:
    sk = build_nm_wa_pilot_rollup_skeleton()
    caps = sk["capabilities"]
    assert caps["batch_classify_match_summary"] is True
    assert caps["conservative_readiness_labels"] is True
    assert caps["missing_data_reporting"] is True
    assert caps["provenance_confidence_reporting"] is True
