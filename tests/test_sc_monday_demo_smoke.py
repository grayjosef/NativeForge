"""Tests: SC Monday demo smoke runner."""

from __future__ import annotations

from nativeforge.services.sc_monday_demo_smoke_runner_service import (
    EXPECTED_SURFACES,
    run_sc_monday_demo_smoke,
)


def test_sc_monday_smoke_pass() -> None:
    result = run_sc_monday_demo_smoke()
    assert result["overall_status"] == "PASS"
    assert result["failures"] == []
    names = [s["surface"] for s in result["surfaces"]]
    for expected in EXPECTED_SURFACES:
        assert expected in names
