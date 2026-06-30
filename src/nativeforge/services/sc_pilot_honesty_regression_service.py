"""SC-5: SC pilot honesty regression."""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services.rt_partial_honesty_regression_service import (
    run_rt_partial_honesty_regression,
)
from nativeforge.services.sc_pilot_fixture_loader_service import fixtures_present

SCHEMA_VERSION = "nf_sc_pilot_honesty_regression_v1"


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def run_sc_pilot_honesty_regression(
    *,
    grants: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    rt = run_rt_partial_honesty_regression(grants=grants or [])
    present = fixtures_present()
    checks = {
        **rt["checks"],
        "sc_pilot_fixtures_present": all(present.values()),
    }
    if not all(present.values()):
        checks["sc_pilot_fixtures_present"] = False
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "fixtures_present": present,
            "checks": checks,
            "verification_passed": all(checks.values()),
            "skip_reason": None
            if all(present.values())
            else "SC pilot fixtures missing — skip integration ACs",
        }
    )
