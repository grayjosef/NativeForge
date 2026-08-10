"""WA-5: WA pilot honesty regression."""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services.rt_partial_honesty_regression_service import (
    run_rt_partial_honesty_regression,
)
from nativeforge.services.sc_pilot_honesty_regression_service import (
    run_sc_pilot_honesty_regression,
)
from nativeforge.services.wa_pilot_fixture_loader_service import fixtures_present

SCHEMA_VERSION = "nf_wa_pilot_honesty_regression_v1"


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def run_wa_pilot_honesty_regression(
    *,
    grants: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    rt = run_rt_partial_honesty_regression(grants=grants)
    sc = run_sc_pilot_honesty_regression(grants=grants)
    present = fixtures_present()
    checks = {
        **rt["checks"],
        **{f"sc_{k}": v for k, v in sc["checks"].items()},
        "wa_pilot_fixtures_present": all(present.values()),
    }
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "fixtures_present": present,
            "checks": checks,
            "verification_passed": all(checks.values()),
            "skip_reason": None
            if all(present.values())
            else "WA pilot fixtures missing — skip integration ACs",
        }
    )
