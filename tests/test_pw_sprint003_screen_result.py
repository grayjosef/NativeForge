"""Sprint 003: Playwright screen result model."""

from __future__ import annotations

import pytest

from nativeforge.services.nm_wa_playwright_e2e_contract_service import (
    empty_playwright_screen_result,
)


def test_screen_result() -> None:
    row = empty_playwright_screen_result("nm_operator_report", status="NOT_RUN")
    assert row["screen"] == "nm_operator_report"


def test_unknown_screen() -> None:
    with pytest.raises(ValueError):
        empty_playwright_screen_result("nope")
