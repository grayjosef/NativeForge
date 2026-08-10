"""WA-19: WA pilot honesty regression."""

from __future__ import annotations

import pytest

from nativeforge.services.wa_pilot_fixture_loader_service import fixtures_present
from nativeforge.services.wa_pilot_honesty_regression_service import (
    run_wa_pilot_honesty_regression,
)


@pytest.mark.skipif(
    not fixtures_present()["profiles"],
    reason="WA pilot fixtures not present",
)
def test_wa_honesty_regression() -> None:
    result = run_wa_pilot_honesty_regression(
        grants=[
            {
                "grant_id": "wa-hon-001",
                "opportunity_title": "Tribal Discretionary Grant",
                "program_area": "health",
            }
        ]
    )
    assert result["verification_passed"]
    assert result["checks"]["wa_pilot_fixtures_present"] is True
