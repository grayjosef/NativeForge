"""Sprint 179: Stage 5 gate verification for funding opportunity intake."""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services import (
    funding_opportunity_intake_demo_fixture_service as fix_svc,
)
from nativeforge.services import (
    funding_opportunity_intake_hardened_record_service as hard_svc,
)

SCHEMA_VERSION = "nf_funding_opportunity_stage5_gate_verification_v1"


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def verify_stage5_gates_on_demo_corpus() -> dict[str, Any]:
    rows = fix_svc.load_demo_fixture_corpus()
    results: list[dict[str, Any]] = []
    blocked_n = 0
    for raw in rows:
        fk = str(raw.get("fixture_key") or "")
        hardened = hard_svc.build_hardened_opportunity_record(raw, fixture_key=fk)
        blocked = bool(hardened["fail_closed_gates"]["fail_closed_blocked"])
        if blocked:
            blocked_n += 1
        results.append(
            {
                "fixture_key": fk,
                "fail_closed_blocked": blocked,
                "intake_status": hardened["intake_status"]["intake_status"],
            }
        )
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "fixture_count": len(rows),
            "blocked_count": blocked_n,
            "results": results,
            "synthetic_only": True,
        }
    )
