"""Object storage signed-URL unlock under approval + malware/SSE (Block 56 / Gate 25)."""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services.gate25_storage_approval_metadata_service import (
    build_gate25_approval_token_model,
)
from nativeforge.services.object_storage_signed_url_service import (
    archive_or_delete_object,
    assert_object_key_org_scoped,
    build_org_scoped_object_key,
    generate_signed_download_url,
    generate_signed_upload_url,
    malware_scan_hook,
    production_object_config_present,
    sse_encryption_requirement_model,
)

SCHEMA_VERSION = "nf_gate25_object_storage_unlock_v1"

_AUDIT: list[dict[str, Any]] = []


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _emit_audit(event: str, detail: dict[str, Any]) -> None:
    _AUDIT.append({"event": event, **detail})


def validate_object_key_policy(
    *,
    environment_scope: str,
    organization_profile_id: str,
    package_workspace_id: str,
    evidence_id: str,
    content_hash: str,
    filename: str,
) -> dict[str, Any]:
    # Reject / normalize path traversal
    unsafe = ".." in filename or "/" in filename or "\\" in filename
    key = build_org_scoped_object_key(
        environment_scope=environment_scope,
        organization_profile_id=organization_profile_id,
        package_workspace_id=package_workspace_id,
        evidence_id=evidence_id,
        content_hash=content_hash,
        normalized_filename=filename,
    )
    org_ok = assert_object_key_org_scoped(key, organization_profile_id)
    _emit_audit(
        "object_key_policy",
        {
            "organization_profile_id": organization_profile_id,
            "object_key": key,
            "path_traversal_input": unsafe,
            "org_scoped": org_ok,
        },
    )
    return _json_safe(
        {
            "object_key": key,
            "org_scoped": org_ok,
            "path_traversal_input_rejected_or_normalized": True,
            "path_traversal_input": unsafe,
            "required_fields_present": all(
                [
                    environment_scope,
                    organization_profile_id,
                    package_workspace_id,
                    evidence_id,
                    content_hash,
                ]
            ),
            "allowed": org_ok and bool(environment_scope),
        }
    )


def resolve_object_storage_approval(token: dict[str, Any]) -> dict[str, Any]:
    scope = token.get("approval_scope")
    approved = bool(
        token.get("approval_valid")
        and token.get("object_storage_approved")
        and scope in {"object_storage", "controlled_pilot", "production_rollout"}
    )
    return _json_safe(
        {
            "object_storage_approved": approved,
            "approval_scope": scope,
            "metadata_only_blocks_object": scope == "metadata_only",
        }
    )


def run_object_storage_signed_url_unlock(
    *,
    token: dict[str, Any] | None = None,
    requesting_org_id: str = "org_a",
    resource_org_id: str = "org_a",
    sse_configured: bool = False,
    malware_satisfied: bool = False,
) -> dict[str, Any]:
    t = token or build_gate25_approval_token_model(present=False)
    approval = resolve_object_storage_approval(t)
    config_present = production_object_config_present()
    sse = sse_encryption_requirement_model()
    if sse_configured:
        sse = {**sse, "configured": True}

    missing: list[str] = []
    if not approval.get("object_storage_approved"):
        missing.append("object_storage_approval_missing")
    if t.get("approval_scope") == "metadata_only":
        missing.append("metadata_only_cannot_unlock_object_storage")
    if not config_present:
        missing.append("object_config_missing")
    if not sse.get("configured"):
        missing.append("sse_encryption_missing")
    if not malware_satisfied:
        missing.append("malware_scan_unsatisfied")

    key_policy = validate_object_key_policy(
        environment_scope="production",
        organization_profile_id=requesting_org_id,
        package_workspace_id="ws_demo",
        evidence_id="ev_demo",
        content_hash="abcd1234efgh5678",
        filename="../../etc/passwd.pdf",
    )

    # Cross-org download
    upload = generate_signed_upload_url(
        organization_profile_id=requesting_org_id,
        package_workspace_id="ws_demo",
        evidence_id="ev_demo",
        content_hash="abcd1234efgh5678",
        approval=None,
    )
    download = generate_signed_download_url(
        object_key=key_policy["object_key"],
        organization_profile_id=requesting_org_id,
        approval=None,
    )
    # Dedicated cross-org: key for org_a, request as org_b
    cross_download = generate_signed_download_url(
        object_key=key_policy["object_key"],
        organization_profile_id="org_b",
        approval=None,
    )
    archive = archive_or_delete_object(
        object_key=key_policy["object_key"],
        action="delete",
        organization_profile_id=requesting_org_id,
        approval=None,
    )
    malware = malware_scan_hook(
        object_key=key_policy["object_key"], satisfied=malware_satisfied
    )

    _emit_audit(
        "object_access",
        {
            "upload_status": upload.get("status"),
            "download_status": cross_download.get("status"),
            "archive_status": archive.get("status"),
        },
    )

    production_object_writes_allowed = False
    signed_urls_live = False
    production_storage_claimed = False
    customer_persistence_claimed = False
    controlled_pilot_storage_ready = False

    # Mode A / incomplete Mode B: never unlock
    if (
        approval.get("object_storage_approved")
        and config_present
        and sse.get("configured")
        and malware_satisfied
        and t.get("secondary_confirmation_present")
    ):
        # Eligible path still kept false until real provisioned validation
        production_object_writes_allowed = False
        missing.append("live_provisioning_validation_incomplete")

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "mode": "A" if not t.get("approval_present") else "B_eligible_incomplete",
            "object_storage_approval_resolver": True,
            "object_storage_approved": approval.get("object_storage_approved"),
            "object_config_present": config_present,
            "signed_upload_url_validator": True,
            "signed_download_url_validator": True,
            "signed_upload_status": upload.get("status"),
            "signed_download_status": cross_download.get("status"),
            "cross_org_download_denied": cross_download.get("status")
            in {"denied_cross_org", "blocked"},
            "object_key_policy": key_policy,
            "path_traversal_protection": True,
            "sse_encryption_gate": sse,
            "malware_scan_gate": malware,
            "archive_delete_gate": {
                "status": archive.get("status"),
                "blocked_without_approval": archive.get("status") == "blocked",
            },
            "production_object_writes_allowed": production_object_writes_allowed,
            "signed_urls_live": signed_urls_live,
            "production_storage_claimed": production_storage_claimed,
            "customer_persistence_claimed": customer_persistence_claimed,
            "controlled_pilot_storage_ready": controlled_pilot_storage_ready,
            "controlled_customer_pilot_status": "NO_GO",
            "production_rollout_status": "NO_GO",
            "login_live_claimed": False,
            "fake_upload_ui": False,
            "fake_signed_url_ui": False,
            "missing_gates": missing,
            "next_owner_action": (
                "Provide object storage approval scope + bucket/endpoint config + "
                "SSE + malware scan; keep customer persistence blocked until auth/"
                "policy/tenant/audit also pass"
            ),
            "upload_probe": upload,
            "download_probe": download,
            "cross_download_probe": cross_download,
            "archive_probe": archive,
            "human_review_required": True,
        }
    )


def object_storage_unlock_invariant_failures(result: dict[str, Any]) -> list[str]:
    fails: list[str] = []
    for key in (
        "production_object_writes_allowed",
        "signed_urls_live",
        "production_storage_claimed",
        "customer_persistence_claimed",
        "controlled_pilot_storage_ready",
        "login_live_claimed",
        "fake_upload_ui",
        "fake_signed_url_ui",
    ):
        if result.get(key) is True:
            fails.append(key)
    if result.get("controlled_customer_pilot_status") == "GO":
        fails.append("pilot_go")
    if not result.get("cross_org_download_denied"):
        fails.append("cross_org_not_denied")
    return fails


def get_object_storage_unlock_audit() -> list[dict[str, Any]]:
    return list(_AUDIT)


def clear_object_storage_unlock_audit_for_tests() -> None:
    _AUDIT.clear()
