"""Sprint 005: validate Playwright smoke honesty invariants."""

from __future__ import annotations

from nativeforge.services.nm_wa_playwright_e2e_contract_service import (
    empty_playwright_smoke_result,
    validate_playwright_smoke_result,
)


def test_not_run_requires_reason() -> None:
    r = empty_playwright_smoke_result(status="NOT_RUN")
    assert "not_run_requires_reason" in validate_playwright_smoke_result(r)


def test_pass_requires_run_id() -> None:
    r = empty_playwright_smoke_result(status="PASS")
    r["overall_status"] = "PASS"
    assert "missing_or_invalid_run_id_for_executed_smoke" in validate_playwright_smoke_result(r)
