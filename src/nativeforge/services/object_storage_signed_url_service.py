"""S3-compatible object storage adapter + signed URL path behind gates (Block 50)."""

from __future__ import annotations

import hashlib
import json
import os
import re
from typing import Any

from nativeforge.services.audit_event_collector_service import (
    AuditEventCollector,
    new_collector,
)
from nativeforge.services.storage_feature_flag_service import (
    build_storage_feature_flag_contract,
)
from nativeforge.services.storage_owner_approval_token_service import (
    build_storage_owner_approval_token,
)

SCHEMA_VERSION = "nf_object_storage_signed_url_v1"
_SAFE_NAME = re.compile(r"[^a-zA-Z0-9._-]+")


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _emit_audit(
    collector: AuditEventCollector, event: str, detail: dict[str, Any]
) -> None:
    collector.record(event, detail)


def production_object_config_present() -> bool:
    return bool(
        os.environ.get("NF_OBJECT_STORAGE_BUCKET")
        and os.environ.get("NF_OBJECT_STORAGE_ENDPOINT")
    )


def build_org_scoped_object_key(
    *,
    environment_scope: str,
    organization_profile_id: str,
    package_workspace_id: str,
    evidence_id: str,
    content_hash: str,
    normalized_filename: str = "file.bin",
) -> str:
    safe_name = _SAFE_NAME.sub("_", normalized_filename).strip("._") or "file.bin"
    # Prevent path traversal / cross-org leakage via filename
    safe_name = safe_name.replace("..", "_")
    ch = content_hash[:16] if content_hash else "nochash"
    return (
        f"{environment_scope}/org/{organization_profile_id}/"
        f"ws/{package_workspace_id}/ev/{evidence_id}/{ch}/{safe_name}"
    )


def assert_object_key_org_scoped(object_key: str, organization_profile_id: str) -> bool:
    needle = f"/org/{organization_profile_id}/"
    return needle in object_key


def _gates(
    *,
    flags: dict[str, Any] | None = None,
    approval: dict[str, Any] | None = None,
) -> dict[str, Any]:
    f = flags or build_storage_feature_flag_contract()
    a = approval or build_storage_owner_approval_token(present=False)
    owner_ok = bool(
        a.get("approval_present")
        and a.get("production_storage_approved")
        and not a.get("revoked")
        and not a.get("stale")
    )
    config_ok = production_object_config_present() or bool(
        f.get("object_storage_config_present")
    )
    signed_ok = bool(f.get("signed_url_config_present")) or bool(
        os.environ.get("NF_OBJECT_STORAGE_SIGNED_URL_ENABLED")
    )
    malware_ok = bool(f.get("malware_scan_config_present")) or bool(
        os.environ.get("NF_MALWARE_SCAN_ENABLED")
    )
    prod_enabled = bool(f.get("production_storage_enabled"))
    writes_allowed = bool(owner_ok and config_ok and prod_enabled and malware_ok)
    signed_allowed = bool(writes_allowed and signed_ok)
    return {
        "owner_approval_present": owner_ok,
        "production_object_config_present": config_ok,
        "signed_url_config_present": signed_ok,
        "malware_scan_config_present": malware_ok,
        "production_storage_enabled": prod_enabled,
        "production_writes_allowed": writes_allowed,
        "signed_url_generation_allowed": signed_allowed,
    }


def malware_scan_hook(*, object_key: str, satisfied: bool = False, collector: AuditEventCollector | None = None) -> dict[str, Any]:
    collector = new_collector(collector)
    status = "passed" if satisfied else "required_not_satisfied"
    _emit_audit(collector, "malware_scan_hook",
        {"object_key": object_key, "status": status},
    )
    return {
        "hook": "malware_scan_v0",
        "status": status,
        "blocks_persistence_if_unsatisfied": True,
        "satisfied": satisfied,
    }


def sse_encryption_requirement_model() -> dict[str, Any]:
    return {
        "required": True,
        "mode": "SSE-S3_or_SSE-KMS",
        "configured": False,
        "production_claim": False,
    }


def generate_signed_upload_url(
    *,
    organization_profile_id: str,
    package_workspace_id: str,
    evidence_id: str,
    content_hash: str,
    flags: dict[str, Any] | None = None,
    approval: dict[str, Any] | None = None,
    collector: AuditEventCollector | None = None,
) -> dict[str, Any]:
    collector = new_collector(collector)
    g = _gates(flags=flags, approval=approval)
    key = build_org_scoped_object_key(
        environment_scope="production",
        organization_profile_id=organization_profile_id,
        package_workspace_id=package_workspace_id,
        evidence_id=evidence_id,
        content_hash=content_hash or hashlib.sha256(b"empty").hexdigest(),
    )
    if not g["signed_url_generation_allowed"]:
        _emit_audit(collector, "signed_upload_url_blocked",
            {"organization_profile_id": organization_profile_id, "object_key": key},
        )
        return _json_safe(
            {
                "status": "blocked",
                "url": None,
                "object_key": key,
                "reasons": [
                    k
                    for k, v in {
                        "owner_approval": g["owner_approval_present"],
                        "object_config": g["production_object_config_present"],
                        "signed_url_config": g["signed_url_config_present"],
                        "malware_scan": g["malware_scan_config_present"],
                        "prod_flag": g["production_storage_enabled"],
                    }.items()
                    if not v
                ],
                "production_storage_claimed": False,
                "customer_data_persistence_claimed": False,
                **g,
            }
        )
    return _json_safe(
        {
            "status": "configured_not_executed",
            "url": None,
            "object_key": key,
            "reasons": ["signed_url_network_call_disabled_in_gate22"],
            "production_storage_claimed": False,
            "customer_data_persistence_claimed": False,
            **g,
        }
    )


def generate_signed_download_url(
    *,
    organization_profile_id: str,
    object_key: str,
    flags: dict[str, Any] | None = None,
    approval: dict[str, Any] | None = None,
    collector: AuditEventCollector | None = None,
) -> dict[str, Any]:
    collector = new_collector(collector)
    g = _gates(flags=flags, approval=approval)
    if not assert_object_key_org_scoped(object_key, organization_profile_id):
        _emit_audit(collector, "signed_download_cross_org_denied",
            {
                "organization_profile_id": organization_profile_id,
                "object_key": object_key,
            },
        )
        return {
            "status": "denied_cross_org",
            "url": None,
            "object_key": object_key,
            "production_storage_claimed": False,
            "customer_data_persistence_claimed": False,
            **g,
        }
    if not g["signed_url_generation_allowed"]:
        _emit_audit(collector, "signed_download_url_blocked",
            {"organization_profile_id": organization_profile_id},
        )
        return {
            "status": "blocked",
            "url": None,
            "object_key": object_key,
            "production_storage_claimed": False,
            "customer_data_persistence_claimed": False,
            **g,
        }
    return {
        "status": "configured_not_executed",
        "url": None,
        "object_key": object_key,
        "production_storage_claimed": False,
        "customer_data_persistence_claimed": False,
        **g,
    }


def archive_or_delete_object(
    *,
    organization_profile_id: str,
    object_key: str,
    action: str = "archive",
    flags: dict[str, Any] | None = None,
    approval: dict[str, Any] | None = None,
    collector: AuditEventCollector | None = None,
) -> dict[str, Any]:
    collector = new_collector(collector)
    g = _gates(flags=flags, approval=approval)
    if not assert_object_key_org_scoped(object_key, organization_profile_id):
        _emit_audit(collector, "object_delete_cross_org_denied",
            {
                "organization_profile_id": organization_profile_id,
                "object_key": object_key,
            },
        )
        return {"status": "denied_cross_org", "action": action, **g}
    if not g["production_writes_allowed"]:
        _emit_audit(collector, f"object_{action}_blocked",
            {
                "organization_profile_id": organization_profile_id,
                "object_key": object_key,
            },
        )
        return {
            "status": "blocked",
            "action": action,
            "audited": True,
            "production_storage_claimed": False,
            **g,
        }
    _emit_audit(collector, f"object_{action}_not_executed",
        {"organization_profile_id": organization_profile_id, "object_key": object_key},
    )
    return {
        "status": "configured_not_executed",
        "action": action,
        "audited": True,
        "production_storage_claimed": False,
        **g,
    }


def build_object_storage_adapter_status(
    *,
    flags: dict[str, Any] | None = None,
    approval: dict[str, Any] | None = None,
    collector: AuditEventCollector | None = None,
) -> dict[str, Any]:
    collector = new_collector(collector)
    g = _gates(flags=flags, approval=approval)
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "adapter": "s3_compatible_object_storage",
            "interface_ready": True,
            "local_dev_object_adapter_compatible": True,
            "signed_upload_url_path": "modeled_behind_gates",
            "signed_download_url_path": "modeled_behind_gates",
            "malware_scan_hook": "present",
            "sse_encryption": sse_encryption_requirement_model(),
            "object_key_scoping": "environment/org/ws/evidence/hash/filename",
            "archive_delete_behavior": "blocked_without_approval_audited",
            "production_writes_allowed": g["production_writes_allowed"],
            "production_storage_claimed": False,
            "customer_data_persistence_claimed": False,
            "audit_events_emitted": len(collector),
            **g,
            "next_safe_action": (
                "Owner approval + NF_OBJECT_STORAGE_BUCKET/ENDPOINT + malware scan "
                "config; keep production writes blocked until validated"
            ),
            "human_review_required": True,
        }
    )


def object_storage_adapter_invariant_failures(result: dict[str, Any]) -> list[str]:
    fails: list[str] = []
    for key in (
        "production_storage_claimed",
        "customer_data_persistence_claimed",
        "production_writes_allowed",
        "signed_url_generation_allowed",
        "owner_approval_present",
    ):
        if result.get(key) is True:
            fails.append(key)
    return fails
