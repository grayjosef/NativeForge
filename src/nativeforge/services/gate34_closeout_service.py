"""Pre-owner closeout packet (Block 82)."""

from __future__ import annotations

import json
from typing import Any

SCHEMA_VERSION = "nf_gate34_closeout_v1"

OWNER_PACKAGE = (
    "auth0_oidc_config",
    "auth0_oidc_secret",
    "auth0_live_validation_enable_flag",
    "storage_approval_token",
    "metadata_storage_config",
    "object_storage_config",
    "signed_url_config",
    "sse_kms_config",
    "malware_scan_config",
    "backup_restore_config",
    "support_owner_assignment",
    "incident_escalation_owner",
)

VENDOR_PACKAGE = (
    "pen_test_report",
    "pen_test_scope",
    "pen_test_findings",
    "pen_test_retest",
)

RERUN = (
    "bash scripts/campaign_block67_smoke_verify.sh  # auth/authority path",
    "bash scripts/campaign_block21_smoke_verify.sh  # storage gates if present",
    "re-run Gate 16 SCA if dependencies change",
    "re-run Gate 13/pen-test validator after report",
    "python -m pytest tests/test_launch_packet_campaign74.py -q  # pilot resolver",
    "bash scripts/sc_monday_demo_staging_verify.sh",
)


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def build_pre_owner_closeout(
    *,
    head: str = "unknown",
    login_live: bool = False,
    production_storage: bool = False,
    pen_test_passed: bool = False,
) -> dict[str, Any]:
    missing_owner = list(OWNER_PACKAGE) if not login_live else []
    if not production_storage:
        missing_owner = list(OWNER_PACKAGE)
    missing_vendor = list(VENDOR_PACKAGE) if not pen_test_passed else []
    blocked = bool(missing_owner or missing_vendor)
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "closeout_packet_contract": True,
            "current_head": head,
            "current_readiness": "~98.4% internal; customer pilot NO_GO",
            "owner_input_package_checklist": list(OWNER_PACKAGE),
            "external_vendor_package_checklist": list(VENDOR_PACKAGE),
            "missing_owner_inputs": missing_owner,
            "missing_vendor_inputs": missing_vendor,
            "remaining_non_owner_work": [
                "keep claim freeze",
                "keep demo honesty panels",
                "do not rehearse missing owner inputs as progress",
            ],
            "post_owner_rerun_sequence": list(RERUN),
            "post_owner_validator_sequence": [
                "auth",
                "storage",
                "pen-test",
                "pilot resolver",
            ],
            "launch_decision_tree": [
                "If any owner input missing -> CONDITIONAL_INTERNAL_ONLY",
                "If pen-test missing -> NO_GO for customer pilot",
                "If auth+storage+pen-test validated -> re-run Gates 29-34 resolvers",
                "Production rollout remains separate review after customer pilot",
            ],
            "controlled_customer_pilot_status": (
                "CONDITIONAL_INTERNAL_ONLY" if blocked else "CONTROLLED_CUSTOMER_GO"
            ),
            "production_rollout_status": "PRODUCTION_ROLLOUT_NO_GO",
            "allowed_claims": [
                "monday_demo_go",
                "pre_owner_closeout_packet",
                "owner_wait_state_exposed",
            ],
            "forbidden_claims": [
                "controlled_customer_pilot_go",
                "production_rollout_go",
                "production-ready",
                "login live",
                "pen-test passed",
            ],
        }
    )


def closeout_invariant_failures(result: dict[str, Any]) -> list[str]:
    fails: list[str] = []
    if "auth0_oidc_config" not in (result.get("owner_input_package_checklist") or []):
        fails.append("owner_list_incomplete")
    if result.get("production_rollout_status") != "PRODUCTION_ROLLOUT_NO_GO":
        fails.append("rollout_not_nogo")
    seq = " ".join(result.get("post_owner_validator_sequence") or [])
    for token in ("auth", "storage", "pen-test", "pilot resolver"):
        if token not in seq:
            fails.append(f"rerun_missing:{token}")
    if (
        result.get("missing_owner_inputs") or result.get("missing_vendor_inputs")
    ) and result.get("controlled_customer_pilot_status") == "CONTROLLED_CUSTOMER_GO":
        fails.append("go_with_missing_inputs")
    return fails
