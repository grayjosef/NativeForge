"""NM-09: NM pilot honesty regression."""

from __future__ import annotations

import pytest

from nativeforge.services.nm_pilot_fixture_loader_service import fixtures_present
from nativeforge.services.nm_pilot_honesty_regression_service import (
    run_nm_pilot_honesty_regression,
)


@pytest.mark.skipif(
    not fixtures_present()["profiles"],
    reason="NM pilot fixtures not present",
)
def test_nm_honesty_regression() -> None:
    result = run_nm_pilot_honesty_regression(
        grants=[
            {
                "grant_id": "nm-hon-001",
                "opportunity_title": "Tribal Discretionary Grant",
                "program_area": "health",
            }
        ]
    )
    assert result["verification_passed"]
    assert result["checks"]["nm_pilot_fixtures_present"] is True
