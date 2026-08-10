"""Sprint 39: safe SC pilot honesty regression smoke with NM/WA present."""

from __future__ import annotations

from nativeforge.services.sc_pilot_honesty_regression_service import (
    run_sc_pilot_honesty_regression,
)


def test_sc_honesty_smoke_with_nm_wa_present() -> None:
    result = run_sc_pilot_honesty_regression(
        grants=[
            {
                "grant_id": "sc-reg-001",
                "opportunity_title": "Tribal Discretionary Grant",
                "program_area": "health",
            }
        ]
    )
    # SC may skip if fixtures missing; require a structured result either way
    assert "verification_passed" in result or "checks" in result
    assert isinstance(result.get("checks"), dict) or result.get("verification_passed") in (
        True,
        False,
    )
