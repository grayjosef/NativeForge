"""Sprint 005: validate smoke result honesty invariants."""

from __future__ import annotations

from nativeforge.services.nm_wa_smoke_validation_contract_service import (
    empty_smoke_result,
    validate_smoke_result,
)


def test_not_run_requires_reason() -> None:
    r = empty_smoke_result(status="NOT_RUN")
    assert "not_run_requires_reason" in validate_smoke_result(r)


def test_pass_requires_valid_run_id() -> None:
    r = empty_smoke_result(status="PASS")
    r["overall_status"] = "PASS"
    assert "missing_or_invalid_run_id_for_executed_smoke" in validate_smoke_result(r)


def test_valid_not_run() -> None:
    r = empty_smoke_result(status="NOT_RUN", not_run_reason="blocked")
    assert validate_smoke_result(r) == []
