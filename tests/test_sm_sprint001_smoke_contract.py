"""Sprint 001: smoke validation contract."""

from __future__ import annotations

from nativeforge.services.nm_wa_smoke_validation_contract_service import (
    EXPECTED_SURFACES,
    build_smoke_validation_contract,
)


def test_smoke_contract() -> None:
    c = build_smoke_validation_contract()
    assert c["offline_only"] is True
    assert c["fabricated_pass_forbidden"] is True
    assert c["fabricated_run_id_forbidden"] is True
    assert c["live_ingestion"] is False
    assert len(c["expected_surfaces"]) == len(EXPECTED_SURFACES)
