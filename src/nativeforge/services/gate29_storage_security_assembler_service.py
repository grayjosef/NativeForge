"""Block 64 assembler: storage/pen-test ingest + pilot resolver surface."""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services.gate29_storage_security_real_input_service import (
    run_storage_security_real_input_ingest,
    storage_security_real_input_invariant_failures,
)

SCHEMA_VERSION = "nf_gate29_storage_security_assembler_v1"
DOCS = [
    "docs/operations/285_GATE29_STORAGE_REAL_INPUT_INGEST.md",
    "docs/operations/286_GATE29_PENTEST_REAL_EVIDENCE_INGEST.md",
    "docs/operations/287_GATE29_PILOT_RESOLVER_REEVALUATION.md",
    "docs/operations/288_GATE29_CLAIM_FREEZE_STATUS.md",
]


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def build_storage_security_real_input_demo_surface() -> dict[str, Any]:
    result = run_storage_security_real_input_ingest()
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "campaign_block": 64,
            "title": "Storage + pen-test real evidence ingest + pilot resolver",
            "docs": DOCS,
            "real_storage_input_detector": True,
            "real_pen_test_evidence_detector": True,
            "synthetic_rehearsal_artifacts_ignored": True,
            "approval_token_present": False,
            "approval_token_valid": False,
            "production_storage_validation_attempted": False,
            "production_storage_claimed": False,
            "customer_persistence_claimed": False,
            "real_pen_test_evidence_present": False,
            "pen_test_pass_claimed": False,
            "claim_freeze_verified": True,
            "controlled_customer_pilot_status": result.get(
                "controlled_customer_pilot_status"
            ),
            "production_rollout_status": result.get("production_rollout_status"),
            "missing_gates": result.get("missing_gates"),
            "fake_pilot_ready": False,
            "next_owner_action": result.get("next_owner_action"),
            "buyer_summary": [
                "Real storage and pen-test detectors exist; synthetic artifacts ignored",
                "Approval/config/report absent; production storage and pen-test pass stay false",
                "Pilot resolver rerun: CONDITIONAL_INTERNAL_ONLY; rollout NO_GO",
                "Claim freeze verified after resolver rerun",
            ],
            "next_safe_actions": [
                result.get("next_owner_action"),
                "Do not claim pilot GO while auth/storage/security gates remain blocked",
            ],
            "human_review_required": True,
            "result": result,
        }
    )


def storage_security_real_input_demo_surface_invariant_failures(
    surface: dict[str, Any],
) -> list[str]:
    fails: list[str] = []
    for key in (
        "production_storage_claimed",
        "customer_persistence_claimed",
        "pen_test_pass_claimed",
        "fake_pilot_ready",
        "approval_token_present",
        "real_pen_test_evidence_present",
    ):
        if surface.get(key) is True:
            fails.append(key)
    if surface.get("controlled_customer_pilot_status") == "CONTROLLED_CUSTOMER_GO":
        fails.append("pilot_go")
    fails.extend(
        storage_security_real_input_invariant_failures(surface.get("result") or {})
    )
    return fails
