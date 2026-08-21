"""Mode B owner unlock packet — Auth0 + storage + pen-test (Block 59 / Gate 27)."""

from __future__ import annotations

import json
import re
from typing import Any

SCHEMA_VERSION = "nf_gate27_owner_unlock_packet_v1"

INPUT_KINDS = (
    "repo_safe_artifact",
    "out_of_band_secret",
    "out_of_band_config",
    "external_report",
    "operator_confirmation",
    "owner_approval",
    "not_allowed_in_repo",
    "unknown",
)

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


def _reject_secret_keys(payload: dict[str, Any]) -> list[str]:
    bad: list[str] = []
    for k in payload:
        if _SECRET_KEY_RE.search(str(k)):
            bad.append(str(k))
    return bad


def build_owner_unlock_packet(
    *,
    auth0_inputs: dict[str, Any] | None = None,
    storage_inputs: dict[str, Any] | None = None,
    security_inputs: dict[str, Any] | None = None,
    repo_safe_artifact: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Prompt alone is never approval; secrets stay out of repo-safe artifacts."""
    auth0 = auth0_inputs or {}
    storage = storage_inputs or {}
    security = security_inputs or {}
    artifact = dict(repo_safe_artifact or {})

    secret_keys = _reject_secret_keys(artifact)
    artifact_rejected = bool(secret_keys)
    if artifact_rejected:
        artifact = {}

    # Auth0 unlock requirements (presence flags only — no secret values)
    auth0_reqs = {
        "issuer_domain": bool(auth0.get("issuer_domain")),
        "audience": bool(auth0.get("audience")),
        "client_id": bool(auth0.get("client_id")),
        "client_secret_present_oob": bool(auth0.get("client_secret_present_oob")),
        "callback_url": bool(auth0.get("callback_url")),
        "logout_url": bool(auth0.get("logout_url")),
        "allowed_origins": bool(auth0.get("allowed_origins")),
        "live_validation_enable_flag": bool(auth0.get("live_validation_enable_flag")),
        "invite_allowlist": bool(auth0.get("invite_allowlist")),
        "org_binding": bool(auth0.get("org_binding")),
        "role_mapping": bool(auth0.get("role_mapping")),
    }
    auth0_complete = all(auth0_reqs.values())

    storage_reqs = {
        "repo_safe_owner_approval_token": bool(
            storage.get("repo_safe_owner_approval_token")
            or artifact.get("approval_present")
        ),
        "metadata_backend_config_oob": bool(storage.get("metadata_backend_config_oob")),
        "object_storage_config_oob": bool(storage.get("object_storage_config_oob")),
        "bucket_key_policy_confirmation": bool(
            storage.get("bucket_key_policy_confirmation")
        ),
        "signed_url_config": bool(storage.get("signed_url_config")),
        "sse_kms_confirmation": bool(storage.get("sse_kms_confirmation")),
        "malware_scan_config": bool(storage.get("malware_scan_config")),
        "backup_restore_config": bool(storage.get("backup_restore_config")),
        "retention_delete_config": bool(storage.get("retention_delete_config")),
    }
    storage_complete = all(storage_reqs.values())

    security_reqs = {
        "pen_test_provider_report_ref": bool(
            security.get("pen_test_provider_report_ref")
        ),
        "test_window": bool(security.get("test_window")),
        "scope": bool(security.get("scope")),
        "findings_summary": bool(security.get("findings_summary")),
        "remediation_status": bool(security.get("remediation_status")),
        "retest_status": bool(security.get("retest_status")),
        "pass_evidence_if_applicable": bool(
            security.get("pass_evidence_if_applicable")
        ),
    }
    # pass evidence optional unless claiming pass — for readiness require report+scope
    security_ready_for_ingest = bool(
        security_reqs["pen_test_provider_report_ref"]
        and security_reqs["test_window"]
        and security_reqs["scope"]
    )

    missing: list[str] = []
    for k, v in auth0_reqs.items():
        if not v:
            missing.append(f"auth0:{k}")
    for k, v in storage_reqs.items():
        if not v:
            missing.append(f"storage:{k}")
    for k in ("pen_test_provider_report_ref", "test_window", "scope"):
        if not security_reqs[k]:
            missing.append(f"security:{k}")

    mode_b_ready = bool(
        auth0_complete
        and storage_complete
        and security_ready_for_ingest
        and not artifact_rejected
    )
    # Mode B-ready ≠ GO — claims stay false until validators pass
    mode = "B_ready_incomplete" if mode_b_ready else "A"

    repo_safe_map = {
        "owner_storage_approval_token_json": "repo_safe_artifact",
        "pen_test_report_reference_path": "repo_safe_artifact",
        "findings_summary_redacted": "repo_safe_artifact",
        "unlock_checklist_status": "repo_safe_artifact",
    }
    oob_map = {
        "OIDC_CLIENT_SECRET": "out_of_band_secret",
        "OIDC_ISSUER": "out_of_band_config",
        "NF_PRODUCTION_METADATA_DATABASE_URL": "out_of_band_config",
        "NF_OBJECT_STORAGE_BUCKET": "out_of_band_config",
        "NF_OBJECT_STORAGE_ENDPOINT": "out_of_band_config",
        "NF_MALWARE_SCAN_ENABLED": "out_of_band_config",
        "SSE_KMS_KEY_REF": "out_of_band_secret",
        "pen_test_full_report_pdf": "external_report",
    }

    # Claims — Mode A / incomplete Mode B always false
    login_live_claimed = False
    production_storage_claimed = False
    pen_test_passed_claimed = False
    customer_persistence_claimed = False
    # Serialize output and ensure no secret-looking values leaked
    result = {
        "schema_version": SCHEMA_VERSION,
        "owner_unlock_packet_contract": True,
        "prompt_alone_is_not_approval": True,
        "mode": mode,
        "mode_b_ready": mode_b_ready,
        "mode_b_executed": False,
        "auth0_unlock_requirements": auth0_reqs,
        "auth0_complete": auth0_complete,
        "storage_unlock_requirements": storage_reqs,
        "storage_complete": storage_complete,
        "pen_test_evidence_requirements": security_reqs,
        "security_ready_for_ingest": security_ready_for_ingest,
        "repo_safe_artifact_map": repo_safe_map,
        "out_of_band_config_secret_map": oob_map,
        "input_kinds": list(INPUT_KINDS),
        "artifact_rejected_for_secrets": artifact_rejected,
        "rejected_secret_keys": secret_keys,
        "missing_owner_inputs": missing,
        "mode_b_execution_checklist": [
            "Place repo-safe approval JSON (no secrets)",
            "Set OIDC_* and storage env out-of-band (never commit)",
            "Attach pen-test report reference + scope/window",
            "Enable live validation flag only after preflight green",
            "Re-run Gate 24–26 resolvers; unlock only gates that pass",
        ],
        "no_secret_validation": True,
        "secrets_in_output": False,
        "login_live_claimed": login_live_claimed,
        "production_auth_claimed": False,
        "production_storage_claimed": production_storage_claimed,
        "customer_persistence_claimed": customer_persistence_claimed,
        "pen_test_passed_claimed": pen_test_passed_claimed,
        "controlled_customer_pilot_status": "CONDITIONAL_INTERNAL_ONLY",
        "production_rollout_status": "PRODUCTION_ROLLOUT_NO_GO",
        "fake_mode_b": False,
        "next_owner_action": (
            "Provide Auth0 OOB config/secrets, repo-safe storage approval, "
            "storage OOB config, and pen-test report reference; then re-run Mode B"
        ),
        "human_review_required": True,
    }

    dumped = json.dumps(result)
    # Heuristic: reject obvious secret values in serialized output
    bad_markers = ("begin rsa private", "sk_live_", "client_secret=")
    if any(s in dumped.lower() for s in bad_markers):
        result["secrets_in_output"] = True
        result["no_secret_validation"] = False

    _emit_audit(
        "owner_unlock_packet_resolve",
        {"mode": mode, "missing_count": len(missing), "mode_b_ready": mode_b_ready},
    )
    return _json_safe(result)


def owner_unlock_packet_invariant_failures(result: dict[str, Any]) -> list[str]:
    fails: list[str] = []
    for key in (
        "login_live_claimed",
        "production_auth_claimed",
        "production_storage_claimed",
        "customer_persistence_claimed",
        "pen_test_passed_claimed",
        "mode_b_executed",
        "fake_mode_b",
        "secrets_in_output",
    ):
        if result.get(key) is True:
            fails.append(key)
    if result.get("mode") == "A" and result.get("mode_b_ready"):
        fails.append("mode_a_with_b_ready")
    if result.get("controlled_customer_pilot_status") == "CONTROLLED_CUSTOMER_GO":
        fails.append("pilot_go")
    return fails


def get_owner_unlock_audit() -> list[dict[str, Any]]:
    return list(_AUDIT)


def clear_owner_unlock_audit_for_tests() -> None:
    _AUDIT.clear()
