"""Sprint 38: safe OK pilot regression smoke alongside NM/WA wiring."""

from __future__ import annotations

import pytest

from nativeforge.services.ok_pilot_fixture_loader_service import fixtures_present
from nativeforge.services.ok_pilot_honesty_regression_service import (
    run_ok_pilot_honesty_regression,
)


@pytest.mark.skipif(
    not fixtures_present()["profiles"],
    reason="OK pilot fixtures not present",
)
def test_ok_honesty_still_passes_with_nm_wa_present() -> None:
    result = run_ok_pilot_honesty_regression(
        grants=[
            {
                "grant_id": "ok-reg-001",
                "opportunity_title": "Tribal Discretionary Grant",
                "program_area": "health",
            }
        ]
    )
    assert result["verification_passed"]
