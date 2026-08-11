"""Sprint 003: browser screen result model."""

from __future__ import annotations

import pytest

from nativeforge.services.nm_wa_browser_demo_contract_service import empty_screen_result


def test_empty_screen_result() -> None:
    row = empty_screen_result("nm_operator_report", status="NOT_RUN", detail="pending")
    assert row["screen"] == "nm_operator_report"
    assert row["status"] == "NOT_RUN"


def test_unknown_screen_rejected() -> None:
    with pytest.raises(ValueError):
        empty_screen_result("not_a_screen")
