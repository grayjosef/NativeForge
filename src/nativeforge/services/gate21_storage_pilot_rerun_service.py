"""Block 48: storage/pilot resolver rerun after approval ingest attempt."""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services.auth0_mode_b_live_unlock_service import (
    run_auth0_mode_b_live_unlock_attempt,
)
from nativeforge.services.controlled_customer_pilot_gate_resolver_service import (
    STATUS_CONTROLLED_GO,
    STATUS_PROD_ROLLOUT_NO_GO,
    resolve_controlled_customer_pilot_gate,
)
from nativeforge.services.pen_test_evidence_capture_service import (
    capture_pen_test_evidence,
)
from nativeforge.services.storage_approval_token_ingest_service import (
    ingest_storage_owner_approval_token,
)
from nativeforge.services.storage_mode_b_execution_service import (
    detect_and_run_storage_mode_b,
)
from nativeforge.services.storage_provisioning_execution_guard_service import (
    evaluate_storage_provisioning_guard,
)

SCHEMA_VERSION = "nf_gate21_storage_pilot_rerun_v1"


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def run_gate21_storage_pilot_rerun() -> dict[str, Any]:
    ingest = ingest_storage_owner_approval_token()
    token = ingest.get("token") or {}
    storage = detect_and_run_storage_mode_b(approval=token)
    guard = evaluate_storage_provisioning_guard(approval=token)
    pen = capture_pen_test_evidence(report_received=False)
    auth = run_auth0_mode_b_live_unlock_attempt()

    provisioning_attempted = bool(
        ingest.get("approval_valid") and storage.get("storage_mode_b_possible")
    )
    # Gate 21 Mode A: no approval file → not attempted
    if not ingest.get("owner_storage_approval_present"):
        provisioning_attempted = False

    pilot = resolve_controlled_customer_pilot_gate(
        login_live=bool(auth.get("login_live_claimed")),
        production_auth=bool(auth.get("production_auth_claimed")),
        storage_ready=False,
        customer_persistence_ready=False,
        full_sca_passed=True,
        pen_test_passed=bool(pen.get("pen_test_passed")),
        owner_approval_present=bool(ingest.get("owner_storage_approval_present")),
        customer_invite_ready=False,
        authority_live=False,
        source_coverage_live=False,
    )

    status = pilot.get("controlled_customer_pilot_status")
    if status == STATUS_CONTROLLED_GO:
        status = "NO_GO"
        pilot = dict(pilot)
        pilot["controlled_customer_pilot_status"] = "NO_GO"

    missing = list(pilot.get("missing_gates") or [])
    if not ingest.get("owner_storage_approval_present"):
        if "owner_approval_absent" not in missing:
            missing.append("owner_approval_absent")

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "campaign_block": 48,
            "ingest": ingest,
            "owner_storage_approval_present": bool(
                ingest.get("owner_storage_approval_present")
            ),
            "approval_valid": bool(ingest.get("approval_valid")),
            "provisioning_validation_attempted": provisioning_attempted,
            "provisioning_guard": {
                "dry_run_allowed": guard.get("dry_run_allowed"),
                "real_provisioning_allowed": guard.get("real_provisioning_allowed"),
                "blocked_reasons": guard.get("blocked_reasons"),
            },
            "production_storage_claimed": False,
            "customer_data_persistence_claimed": False,
            "pen_test_evidence_captured": bool(pen.get("evidence_captured")),
            "pen_test_passed": False,
            "final_controlled_pilot_status": status,
            "production_rollout_status": STATUS_PROD_ROLLOUT_NO_GO,
            "missing_gates": missing,
            "auth_unlock_mode": auth.get("mode_detected"),
            "login_live_claimed": False,
            "owner_next_actions": [
                ingest.get("next_safe_action"),
                "Attach real pen-test report artifact when available",
                "Complete Auth0 Mode B unlock (Block 47) before pilot GO",
                "Re-run bash scripts/campaign_block48_smoke_verify.sh",
            ],
            "human_review_required": True,
        }
    )


def gate21_storage_pilot_rerun_invariant_failures(result: dict[str, Any]) -> list[str]:
    fails: list[str] = []
    for key in (
        "production_storage_claimed",
        "customer_data_persistence_claimed",
        "pen_test_passed",
        "login_live_claimed",
        "provisioning_validation_attempted",
        "owner_storage_approval_present",
        "approval_valid",
    ):
        if result.get(key) is True:
            fails.append(key)
    if result.get("final_controlled_pilot_status") in {
        STATUS_CONTROLLED_GO,
        "CONTROLLED_CUSTOMER_GO",
        "GO",
    }:
        fails.append("pilot_go")
    return fails
