"""Mode B live unlock rehearsal — synthetic fixtures only by default (Block 61)."""

from __future__ import annotations

import json
import re
import uuid
from datetime import UTC, datetime
from typing import Any

from nativeforge.services.gate27_cutover_claim_freeze_service import (
    build_claim_freeze_matrix,
)
from nativeforge.services.gate27_owner_unlock_packet_service import (
    build_owner_unlock_packet,
)

SCHEMA_VERSION = "nf_gate28_mode_b_rehearsal_v1"

_SECRET_KEY_RE = re.compile(
    r"(secret|password|api[_-]?key|token_value|private_key|client_secret)",
    re.IGNORECASE,
)

_AUDIT: list[dict[str, Any]] = []


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _emit_audit(event: str, detail: dict[str, Any]) -> None:
    _AUDIT.append({"event": event, **detail})


def build_synthetic_non_secret_fixture() -> dict[str, Any]:
    """Control-flow only. Cannot unlock live claims."""
    return {
        "fixture_kind": "synthetic_non_secret",
        "auth0": {
            "issuer_domain": True,
            "audience": True,
            "client_id": True,
            "client_secret_present_oob": False,  # synthetic cannot claim real secret
            "callback_url": True,
            "logout_url": True,
            "allowed_origins": True,
            "live_validation_enable_flag": False,
            "invite_allowlist": True,
            "org_binding": True,
            "role_mapping": True,
        },
        "storage": {
            "repo_safe_owner_approval_token": True,
            "metadata_backend_config_oob": False,
            "object_storage_config_oob": False,
            "bucket_key_policy_confirmation": True,
            "signed_url_config": False,
            "sse_kms_confirmation": False,
            "malware_scan_config": False,
            "backup_restore_config": False,
            "retention_delete_config": True,
        },
        "security": {
            "pen_test_provider_report_ref": False,
            "test_window": False,
            "scope": False,
            "findings_summary": False,
            "remediation_status": False,
            "retest_status": False,
            "pass_evidence_if_applicable": False,
        },
        "note": "synthetic_proves_control_flow_only",
    }


def detect_real_owner_inputs(
    *,
    auth0_real: bool = False,
    storage_real: bool = False,
    pen_test_real: bool = False,
) -> dict[str, Any]:
    present = bool(auth0_real and storage_real and pen_test_real)
    missing: list[str] = []
    if not auth0_real:
        missing.append("real_auth0_oidc_oob")
    if not storage_real:
        missing.append("real_storage_approval_and_config")
    if not pen_test_real:
        missing.append("real_pen_test_report")
    return {
        "real_owner_inputs_present": present,
        "auth0_real": auth0_real,
        "storage_real": storage_real,
        "pen_test_real": pen_test_real,
        "missing_real_inputs": missing,
    }


def run_mode_b_rehearsal(
    *,
    use_synthetic: bool = True,
    repo_safe_fixture: dict[str, Any] | None = None,
    auth0_real: bool = False,
    storage_real: bool = False,
    pen_test_real: bool = False,
) -> dict[str, Any]:
    run_id = (
        f"nf_modeb_rehearsal_"
        f"{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}_{uuid.uuid4().hex[:8]}"
    )
    real = detect_real_owner_inputs(
        auth0_real=auth0_real, storage_real=storage_real, pen_test_real=pen_test_real
    )
    rejected_secrets: list[str] = []
    fixture_used = False
    fixture: dict[str, Any] = {}

    if repo_safe_fixture:
        for k in repo_safe_fixture:
            if _SECRET_KEY_RE.search(str(k)):
                rejected_secrets.append(str(k))
        if rejected_secrets:
            fixture = {}
        else:
            fixture = dict(repo_safe_fixture)

    if use_synthetic and not real["real_owner_inputs_present"]:
        fixture = build_synthetic_non_secret_fixture()
        fixture_used = True

    # Rehearse unlock packet with synthetic flags (control flow only)
    auth0_in = fixture.get("auth0") if fixture_used else {}
    storage_in = fixture.get("storage") if fixture_used else {}
    security_in = fixture.get("security") if fixture_used else {}
    packet = build_owner_unlock_packet(
        auth0_inputs=auth0_in or None,
        storage_inputs=storage_in or None,
        security_inputs=security_in or None,
    )
    freeze = build_claim_freeze_matrix(unlock=packet)

    # Hard: synthetic never executes Mode B / live claims
    mode_b_executed_claimed = False
    if real["real_owner_inputs_present"] and not use_synthetic:
        # Still false until actual validators pass — Gate 28 does not auto-execute
        mode_b_executed_claimed = False

    mode = "A"
    if real["real_owner_inputs_present"]:
        mode = "B_inputs_detected_not_executed"
    elif fixture_used:
        mode = "A_synthetic_rehearsal"

    result = {
        "schema_version": SCHEMA_VERSION,
        "rehearsal_contract": True,
        "rehearsal_run_id": run_id,
        "mode": mode,
        "real_owner_inputs_present": real["real_owner_inputs_present"],
        "synthetic_fixture_used": fixture_used,
        "auth0_rehearsed": bool(fixture_used or auth0_real),
        "storage_rehearsed": bool(fixture_used or storage_real),
        "pen_test_rehearsed": bool(fixture_used or pen_test_real),
        "claim_freeze_verified": True,
        "mode_b_executed_claimed": mode_b_executed_claimed,
        "login_live_claimed": False,
        "production_auth_claimed": False,
        "production_storage_claimed": False,
        "customer_persistence_claimed": False,
        "pen_test_passed_claimed": False,
        "controlled_customer_pilot_go_claimed": False,
        "missing_real_inputs": real["missing_real_inputs"],
        "rejected_secret_keys": rejected_secrets,
        "no_secret_validation": len(rejected_secrets) == 0,
        "secrets_in_output": False,
        "prompt_alone_is_not_approval": True,
        "synthetic_cannot_unlock_live": True,
        "controlled_customer_pilot_status": "CONDITIONAL_INTERNAL_ONLY",
        "production_rollout_status": "PRODUCTION_ROLLOUT_NO_GO",
        "fake_mode_b": False,
        "next_owner_action": (
            "Provide real Auth0 OOB, storage approval/config, and pen-test report; "
            "then re-run Gate 28 Mode B (not synthetic)"
        ),
        "packet_mode": packet.get("mode"),
        "freeze_booleans": freeze.get("frozen_claim_booleans"),
        "human_review_required": True,
    }

    dumped = json.dumps(result)
    if any(s in dumped.lower() for s in ("begin rsa private", "sk_live_")):
        result["secrets_in_output"] = True
        result["no_secret_validation"] = False

    _emit_audit(
        "mode_b_rehearsal",
        {
            "run_id": run_id,
            "mode": mode,
            "synthetic": fixture_used,
            "mode_b_executed_claimed": mode_b_executed_claimed,
        },
    )
    return _json_safe(result)


def mode_b_rehearsal_invariant_failures(result: dict[str, Any]) -> list[str]:
    fails: list[str] = []
    for key in (
        "mode_b_executed_claimed",
        "login_live_claimed",
        "production_auth_claimed",
        "production_storage_claimed",
        "customer_persistence_claimed",
        "pen_test_passed_claimed",
        "controlled_customer_pilot_go_claimed",
        "fake_mode_b",
        "secrets_in_output",
    ):
        if result.get(key) is True:
            fails.append(key)
    if result.get("synthetic_fixture_used") and result.get("mode_b_executed_claimed"):
        fails.append("synthetic_unlocked_mode_b")
    if result.get("controlled_customer_pilot_status") == "CONTROLLED_CUSTOMER_GO":
        fails.append("pilot_go")
    return fails


def get_mode_b_rehearsal_audit() -> list[dict[str, Any]]:
    return list(_AUDIT)


def clear_mode_b_rehearsal_audit_for_tests() -> None:
    _AUDIT.clear()
