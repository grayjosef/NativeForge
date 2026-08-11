"""Sprint 033: execute offline smoke runner."""

from __future__ import annotations

from nativeforge.services.nm_wa_smoke_runner_service import (
    run_nm_wa_operator_surfacing_smoke,
)
from nativeforge.services.nm_wa_smoke_validation_contract_service import validate_run_id


def test_run_smoke_pass() -> None:
    r = run_nm_wa_operator_surfacing_smoke()
    assert r["overall_status"] == "PASS"
    assert validate_run_id(r["run_id"])
    assert r["failures"] == []
    assert all(s["status"] == "PASS" for s in r["surfaces"])
