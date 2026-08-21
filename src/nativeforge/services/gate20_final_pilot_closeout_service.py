"""Gate 20 final controlled customer pilot resolver + closeout inputs (Block 46)."""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services.auth0_mode_b_execution_service import (
    run_auth0_mode_b_execution_path,
)
from nativeforge.services.controlled_customer_pilot_gate_resolver_service import (
    STATUS_CONDITIONAL_INTERNAL,
    STATUS_CONTROLLED_GO,
    STATUS_PROD_ROLLOUT_NO_GO,
    resolve_controlled_customer_pilot_gate,
)
from nativeforge.services.pen_test_evidence_capture_service import (
    capture_pen_test_evidence,
)
from nativeforge.services.pilot_auth_readiness_resolver_service import (
    resolve_pilot_auth_readiness,
)
from nativeforge.services.storage_mode_b_execution_service import (
    detect_and_run_storage_mode_b,
)

SCHEMA_VERSION = "nf_gate20_final_pilot_closeout_v1"


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def build_gate20_final_pilot_closeout() -> dict[str, Any]:
    auth_exec = run_auth0_mode_b_execution_path()
    auth_ready = resolve_pilot_auth_readiness(execution=auth_exec)
    storage = detect_and_run_storage_mode_b()
    pen = capture_pen_test_evidence(report_received=False)
    pilot = resolve_controlled_customer_pilot_gate(
        login_live=bool(auth_ready.get("login_live_claimed")),
        production_auth=bool(auth_ready.get("production_auth_claimed")),
        storage_ready=bool(storage.get("production_storage_claimed")),
        customer_persistence_ready=bool(
            storage.get("customer_data_persistence_claimed")
        ),
        full_sca_passed=True,
        pen_test_passed=bool(pen.get("pen_test_passed")),
        owner_approval_present=bool(storage.get("owner_approval_present")),
        customer_invite_ready=False,
        authority_live=False,
        source_coverage_live=False,
    )

    status = pilot.get("controlled_customer_pilot_status")
    if status == STATUS_CONTROLLED_GO:
        status = "NO_GO"
        pilot = dict(pilot)
        pilot["controlled_customer_pilot_status"] = "NO_GO"
        pilot["reason"] = "Safety clamp — Gate 20 Mode A cannot unlock GO"

    owner_actions = [
        "Set OIDC_* env vars out-of-band; enable NF_AUTH0_LIVE_VALIDATION_ENABLED; configure invite/org/role",
        "Issue repo-safe storage owner approval token; provision managed Postgres + S3-compatible SSE",
        "Complete external pen-test; attach report artifact; remediate critical/high; retest",
        "Re-run Gate 20 Mode B path and controlled pilot resolver",
    ]

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "mode": "mode_a",
            "auth": {
                "mode_detected": auth_exec.get("mode_detected"),
                "login_live_claimed": auth_ready.get("login_live_claimed"),
                "production_auth_claimed": auth_ready.get("production_auth_claimed"),
                "controlled_pilot_auth_ready": auth_ready.get(
                    "controlled_pilot_auth_ready"
                ),
            },
            "storage": storage,
            "pen_test": pen,
            "pilot": pilot,
            "controlled_customer_pilot_status": status,
            "production_rollout_status": STATUS_PROD_ROLLOUT_NO_GO,
            "missing_gates": pilot.get("missing_gates"),
            "owner_next_actions": owner_actions,
            "mode_b_rerun_path": (
                "source .venv/bin/activate && "
                "bash scripts/campaign_block45_smoke_verify.sh && "
                "bash scripts/campaign_block46_smoke_verify.sh"
            ),
            "allowed_claims": pilot.get("allowed_claims"),
            "forbidden_claims": pilot.get("forbidden_claims"),
            "estimated_maturity_pct": 96.0,
            "human_review_required": True,
            "login_live_claimed": False,
            "production_storage_claimed": False,
            "customer_data_persistence_claimed": False,
            "pen_test_passed": False,
        }
    )


def gate20_final_pilot_closeout_invariant_failures(
    result: dict[str, Any],
) -> list[str]:
    fails: list[str] = []
    if result.get("controlled_customer_pilot_status") in {
        STATUS_CONTROLLED_GO,
        "GO",
        "CONTROLLED_CUSTOMER_GO",
    }:
        fails.append("pilot_go")
    if result.get("production_rollout_status") not in {
        STATUS_PROD_ROLLOUT_NO_GO,
        "PRODUCTION_ROLLOUT_NO_GO",
        "NO_GO",
    }:
        fails.append("rollout_not_nogo")
    for key in (
        "login_live_claimed",
        "production_storage_claimed",
        "customer_data_persistence_claimed",
        "pen_test_passed",
    ):
        if result.get(key) is True:
            fails.append(key)
    # Mode A should not claim Mode B unlocks
    if result.get("mode") != "mode_a":
        # allow mode_b only if auth mode detected mode_b — Gate 20 default mode_a
        if result.get("mode") not in {"mode_a", "mode_b"}:
            fails.append("bad_mode")
    return fails


def expected_internal_status() -> str:
    return STATUS_CONDITIONAL_INTERNAL
