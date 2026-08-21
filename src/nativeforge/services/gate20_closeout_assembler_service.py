"""Block 46 assembler: storage Mode B + pen-test + 2000-sprint closeout surface."""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services.gate20_final_pilot_closeout_service import (
    build_gate20_final_pilot_closeout,
    gate20_final_pilot_closeout_invariant_failures,
)
from nativeforge.services.pen_test_evidence_capture_service import (
    pen_test_evidence_capture_invariant_failures,
)
from nativeforge.services.storage_mode_b_execution_service import (
    storage_mode_b_execution_invariant_failures,
)

SCHEMA_VERSION = "nf_gate20_closeout_assembler_v1"
DOCS = [
    "docs/operations/230_GATE20_PEN_TEST_EVIDENCE_CAPTURE.md",
    "docs/operations/231_NATIVEFORGE_2000_SPRINT_CLOSEOUT_REPORT.md",
]


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def build_gate20_closeout_demo_surface() -> dict[str, Any]:
    closeout = build_gate20_final_pilot_closeout()
    storage = closeout.get("storage") or {}
    pen = closeout.get("pen_test") or {}
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "campaign_block": 46,
            "title": "Storage Mode B + pen-test evidence + 2000-sprint closeout",
            "docs": DOCS,
            "mode": closeout.get("mode"),
            "storage_mode_b_possible": bool(storage.get("storage_mode_b_possible")),
            "owner_approval_present": bool(storage.get("owner_approval_present")),
            "approval_valid": bool(storage.get("approval_valid")),
            "provisioning_validation_attempted": bool(
                storage.get("provisioning_validation_attempted")
            ),
            "production_storage_claimed": False,
            "customer_data_persistence_claimed": False,
            "controlled_pilot_storage_ready": False,
            "pen_test_evidence_captured": bool(pen.get("evidence_captured")),
            "pen_test_passed_claim": False,
            "critical_high_findings_open": int(pen.get("critical_high_open") or 0),
            "controlled_customer_pilot_status": closeout.get(
                "controlled_customer_pilot_status"
            ),
            "production_rollout_status": closeout.get("production_rollout_status"),
            "missing_gates": closeout.get("missing_gates"),
            "owner_next_actions": closeout.get("owner_next_actions"),
            "mode_b_rerun_path": closeout.get("mode_b_rerun_path"),
            "estimated_maturity_pct": closeout.get("estimated_maturity_pct"),
            "login_live_claimed": False,
            "buyer_summary": [
                "Storage Mode B blocked without owner approval/config",
                "Pen-test evidence absent — pen_test_passed remains false",
                "Controlled customer pilot remains NO_GO / CONDITIONAL_INTERNAL_ONLY",
                "2000-sprint closeout report documents exact owner next actions",
            ],
            "next_safe_actions": list(closeout.get("owner_next_actions") or []),
            "human_review_required": True,
            "closeout": closeout,
        }
    )


def gate20_closeout_demo_surface_invariant_failures(
    surface: dict[str, Any],
) -> list[str]:
    fails: list[str] = []
    for key in (
        "storage_mode_b_possible",
        "owner_approval_present",
        "provisioning_validation_attempted",
        "production_storage_claimed",
        "customer_data_persistence_claimed",
        "controlled_pilot_storage_ready",
        "pen_test_evidence_captured",
        "pen_test_passed_claim",
        "login_live_claimed",
    ):
        if surface.get(key) is True:
            fails.append(key)
    if surface.get("controlled_customer_pilot_status") in {
        "CONTROLLED_CUSTOMER_GO",
        "GO",
    }:
        fails.append("pilot_go")
    fails.extend(
        storage_mode_b_execution_invariant_failures(
            surface.get("closeout", {}).get("storage") or {}
        )
    )
    fails.extend(
        pen_test_evidence_capture_invariant_failures(
            surface.get("closeout", {}).get("pen_test") or {}
        )
    )
    fails.extend(
        gate20_final_pilot_closeout_invariant_failures(surface.get("closeout") or {})
    )
    return fails
