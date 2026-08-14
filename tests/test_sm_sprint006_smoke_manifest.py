"""Sprint 006: smoke manifest."""

from __future__ import annotations

from nativeforge.services.nm_wa_smoke_manifest_service import build_smoke_manifest
from nativeforge.services.nm_wa_smoke_validation_contract_service import (
    EXPECTED_SURFACES,
)


def test_smoke_manifest() -> None:
    m = build_smoke_manifest()
    assert m["mode"] == "offline_synthetic"
    assert m["expected_surfaces"] == list(EXPECTED_SURFACES)
    assert "missing_combined_review_queue" in m["hard_stops"]
    assert len(m["checklist"]) == len(EXPECTED_SURFACES)
