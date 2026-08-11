"""Sprint 005: validate browser smoke honesty invariants."""

from __future__ import annotations

from nativeforge.services.nm_wa_browser_demo_contract_service import (
    empty_browser_smoke_result,
    validate_browser_smoke_result,
)


def test_not_run_requires_reason() -> None:
    r = empty_browser_smoke_result(status="NOT_RUN")
    assert "not_run_requires_reason" in validate_browser_smoke_result(r)


def test_pass_requires_run_id() -> None:
    r = empty_browser_smoke_result(status="PASS")
    r["overall_status"] = "PASS"
    assert "missing_or_invalid_run_id_for_executed_smoke" in validate_browser_smoke_result(r)


def test_valid_not_run() -> None:
    r = empty_browser_smoke_result(status="NOT_RUN", not_run_reason="blocked")
    assert validate_browser_smoke_result(r) == []
