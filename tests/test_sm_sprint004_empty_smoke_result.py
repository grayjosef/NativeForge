"""Sprint 004: empty smoke result scaffold."""

from __future__ import annotations

from nativeforge.services.nm_wa_smoke_validation_contract_service import (
    EXPECTED_SURFACES,
    empty_smoke_result,
)


def test_empty_smoke_result_covers_all_surfaces() -> None:
    r = empty_smoke_result(status="NOT_RUN", not_run_reason="scaffold")
    assert len(r["surfaces"]) == len(EXPECTED_SURFACES)
    assert r["overall_status"] == "NOT_RUN"
    assert r["not_run_reason"] == "scaffold"
