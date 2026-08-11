"""Sprint 002: smoke run_id format validation."""

from __future__ import annotations

from nativeforge.services.nm_wa_smoke_validation_contract_service import validate_run_id


def test_run_id_format() -> None:
    assert validate_run_id("nf_os_smoke_20260810T123456Z_abcd1234")
    assert not validate_run_id("fake")
    assert not validate_run_id("nf_os_smoke_bad")
