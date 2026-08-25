"""Production metadata adapter behind flags — blocked without approval/config (Block 49)."""

from __future__ import annotations

import json
import os
from typing import Any

from nativeforge.services.audit_event_collector_service import (
    AuditEventCollector,
    new_collector,
)
from nativeforge.services.evidence_metadata_model_service import (
    build_evidence_metadata_record,
)
from nativeforge.services.storage_feature_flag_service import (
    build_storage_feature_flag_contract,
)
from nativeforge.services.storage_owner_approval_token_service import (
    build_storage_owner_approval_token,
)

SCHEMA_VERSION = "nf_production_metadata_adapter_v1"

# In-memory local/dev store only (never production)
_LOCAL_DEV_STORE: dict[str, dict[str, Any]] = {}


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _emit_audit(
    collector: AuditEventCollector, event: str, detail: dict[str, Any]
) -> None:
    collector.record(event, detail)


def production_metadata_config_present() -> bool:
    return bool(
        os.environ.get("NF_PRODUCTION_METADATA_DATABASE_URL")
        or os.environ.get("DATABASE_URL_PRODUCTION_METADATA")
    )


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
    config_ok = production_metadata_config_present() or bool(
        f.get("metadata_db_config_present")
    )
    prod_enabled = bool(f.get("production_storage_enabled"))
    allowed = bool(owner_ok and config_ok and prod_enabled)
    return {
        "owner_approval_present": owner_ok,
        "production_metadata_config_present": config_ok,
        "production_storage_enabled": prod_enabled,
        "production_metadata_writes_allowed": allowed,
    }


def local_dev_metadata_write(
    *,
    organization_profile_id: str,
    package_workspace_id: str = "ws_default",
    original_filename: str = "evidence.pdf",
    collector: AuditEventCollector | None = None,
) -> dict[str, Any]:
    collector = new_collector(collector)
    rec = build_evidence_metadata_record(
        organization_profile_id=organization_profile_id,
        package_workspace_id=package_workspace_id,
        original_filename=original_filename,
        environment_scope="local_dev",
        customer_data_scope="none",
    )
    rec["storage_backend"] = "local_dev_validated_persistent"
    _LOCAL_DEV_STORE[rec["evidence_id"]] = rec
    _emit_audit(
        collector,
        "local_dev_metadata_write",
        {
            "evidence_id": rec["evidence_id"],
            "organization_profile_id": organization_profile_id,
            "status": "allowed",
        },
    )
    return _json_safe({"status": "ok", "record": rec, "mode": "local_dev"})


def local_dev_metadata_read(
    *,
    evidence_id: str,
    requesting_org_id: str,
    collector: AuditEventCollector | None = None,
) -> dict[str, Any]:
    collector = new_collector(collector)
    rec = _LOCAL_DEV_STORE.get(evidence_id)
    if not rec:
        return {"status": "not_found", "record": None}
    if rec.get("organization_profile_id") != requesting_org_id:
        _emit_audit(
            collector,
            "local_dev_metadata_cross_org_denied",
            {
                "evidence_id": evidence_id,
                "requesting_org_id": requesting_org_id,
                "owner_org_id": rec.get("organization_profile_id"),
            },
        )
        return {"status": "denied_cross_org", "record": None}
    return {"status": "ok", "record": rec}


def production_metadata_write_attempt(
    *,
    organization_profile_id: str,
    flags: dict[str, Any] | None = None,
    approval: dict[str, Any] | None = None,
    collector: AuditEventCollector | None = None,
) -> dict[str, Any]:
    collector = new_collector(collector)
    g = _gates(flags=flags, approval=approval)
    if not g["production_metadata_writes_allowed"]:
        reasons = []
        if not g["owner_approval_present"]:
            reasons.append("owner_approval_absent")
        if not g["production_metadata_config_present"]:
            reasons.append("metadata_config_absent")
        if not g["production_storage_enabled"]:
            reasons.append("production_storage_flag_off")
        _emit_audit(
            collector,
            "production_metadata_write_blocked",
            {
                "organization_profile_id": organization_profile_id,
                "reasons": reasons,
            },
        )
        return _json_safe(
            {
                "schema_version": SCHEMA_VERSION,
                "status": "blocked",
                "mode": "production",
                "reasons": reasons,
                "record": None,
                "production_storage_claimed": False,
                "customer_data_persistence_claimed": False,
                **g,
            }
        )
    # Even if gates modeled green, Gate 22 does not perform real production writes
    _emit_audit(
        collector,
        "production_metadata_write_not_executed",
        {"organization_profile_id": organization_profile_id},
    )
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "status": "configured_not_executed",
            "mode": "production",
            "reasons": ["network_production_write_disabled_in_gate22"],
            "record": None,
            "production_storage_claimed": False,
            "customer_data_persistence_claimed": False,
            **g,
        }
    )


def build_production_metadata_adapter_status(
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
            "adapter": "managed_postgres_metadata",
            "interface_ready": True,
            "local_dev_metadata_allowed": True,
            "dry_run_mode": True,
            "blocked_production_mode": not g["production_metadata_writes_allowed"],
            "tenant_org_scoping": True,
            "audit_linkage": True,
            "retention_delete_linkage": True,
            "production_storage_claimed": False,
            "customer_data_persistence_claimed": False,
            "audit_events_emitted": len(collector),
            **g,
            "next_safe_action": (
                "Obtain owner approval + set NF_PRODUCTION_METADATA_DATABASE_URL "
                "out-of-band; keep production_storage_enabled=false until validated"
            ),
            "human_review_required": True,
        }
    )


def production_metadata_adapter_invariant_failures(
    result: dict[str, Any],
) -> list[str]:
    fails: list[str] = []
    for key in (
        "production_storage_claimed",
        "customer_data_persistence_claimed",
        "production_metadata_writes_allowed",
        "owner_approval_present",
    ):
        if result.get(key) is True:
            fails.append(key)
    return fails


def clear_local_dev_metadata_store_for_tests() -> None:
    _LOCAL_DEV_STORE.clear()
