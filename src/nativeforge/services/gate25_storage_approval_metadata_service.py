"""Storage owner approval ingest + production metadata live path (Block 55 / Gate 25)."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from typing import Any

from nativeforge.services.production_metadata_adapter_service import (
    production_metadata_config_present,
    production_metadata_write_attempt,
)
from nativeforge.services.storage_approval_token_ingest_service import (
    ingest_storage_owner_approval_token,
)

SCHEMA_VERSION = "nf_gate25_storage_approval_metadata_v1"

APPROVAL_SCOPES = (
    "none",
    "invalid",
    "expired",
    "revoked",
    "dry_run_only",
    "metadata_only",
    "object_storage",
    "controlled_pilot",
    "production_rollout",
)

_AUDIT: list[dict[str, Any]] = []


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _emit_audit(event: str, detail: dict[str, Any]) -> None:
    _AUDIT.append({"event": event, **detail})


def build_gate25_approval_token_model(
    *,
    present: bool = False,
    revoked: bool = False,
    expired: bool = False,
    scope: str = "none",
    metadata_approved: bool = False,
    object_storage_approved: bool = False,
    customer_persistence_approved: bool = False,
    controlled_pilot_approved: bool = False,
    production_rollout_approved: bool = False,
    secondary_confirmation_present: bool = False,
) -> dict[str, Any]:
    now = datetime.now(UTC)
    sc = scope if scope in APPROVAL_SCOPES else "invalid"
    expires_at = None
    if present and not expired:
        expires_at = (now + timedelta(hours=24)).isoformat().replace("+00:00", "Z")
    if expired:
        expires_at = (now - timedelta(hours=1)).isoformat().replace("+00:00", "Z")

    if not present:
        sc = "none"
        metadata_approved = False
        object_storage_approved = False
        customer_persistence_approved = False
        controlled_pilot_approved = False
        production_rollout_approved = False

    if revoked:
        sc = "revoked"
        metadata_approved = False
        object_storage_approved = False
        customer_persistence_approved = False
        controlled_pilot_approved = False
        production_rollout_approved = False

    if expired and present:
        sc = "expired"
        metadata_approved = False
        object_storage_approved = False
        customer_persistence_approved = False
        controlled_pilot_approved = False
        production_rollout_approved = False

    # Scope discipline
    if sc == "dry_run_only":
        metadata_approved = False
        object_storage_approved = False
        customer_persistence_approved = False
        controlled_pilot_approved = False
        production_rollout_approved = False
    elif sc == "metadata_only":
        metadata_approved = True
        object_storage_approved = False
        customer_persistence_approved = False
        production_rollout_approved = False

    valid = bool(
        present
        and not revoked
        and not expired
        and sc
        not in {"none", "invalid", "expired", "revoked"}
    )

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "approval_id": "soat_gate25_absent" if not present else f"soat_g25_{sc}",
            "approved_by": "owner" if present else "",
            "approved_at": now.isoformat().replace("+00:00", "Z") if present else None,
            "expires_at": expires_at,
            "revoked": revoked,
            "approval_source": "owner_file" if present else "none",
            "approved_environment": "production" if present else "local_dev",
            "approved_backend": "managed_postgres_s3" if present else "none",
            "approved_actions": ["dry_run_review"] if present else [],
            "excluded_actions": [
                "mutate_customer_data",
                "enable_customer_persistence_without_validation",
            ],
            "secondary_confirmation_required": True,
            "secondary_confirmation_present": secondary_confirmation_present,
            "metadata_approved": metadata_approved,
            "object_storage_approved": object_storage_approved,
            "customer_persistence_approved": customer_persistence_approved,
            "controlled_pilot_approved": controlled_pilot_approved,
            "production_rollout_approved": production_rollout_approved,
            "approval_scope": sc,
            "approval_present": present,
            "approval_valid": valid,
            "approval_alone_does_not_validate": True,
            "prompt_alone_is_not_approval": True,
        }
    )


def resolve_approval_scope(token: dict[str, Any]) -> str:
    return str(token.get("approval_scope") or "none")


def validate_production_metadata_live_path(
    *,
    token: dict[str, Any] | None = None,
    rbac_ok: bool = True,
    tenant_ok: bool = True,
    audit_ok: bool = True,
    customer_policy_ok: bool = False,
    login_live: bool = False,
    attempt_write: bool = True,
) -> dict[str, Any]:
    """Mode A default: no token → blocked. Prompt text is never approval."""
    ingest = ingest_storage_owner_approval_token()
    t = token or build_gate25_approval_token_model(present=False)

    # Prefer explicit test token; otherwise merge ingest absence
    if token is None and not ingest.get("approval_valid"):
        t = build_gate25_approval_token_model(present=False)

    missing: list[str] = []
    if not t.get("approval_present"):
        missing.append("approval_token_missing")
    if t.get("revoked"):
        missing.append("approval_revoked")
    if t.get("approval_scope") == "expired" or (
        t.get("expires_at")
        and t.get("approval_scope") == "expired"
    ):
        missing.append("approval_expired")
    if t.get("approval_scope") == "dry_run_only":
        missing.append("dry_run_approval_cannot_unlock_production")
    if not t.get("metadata_approved"):
        missing.append("metadata_not_approved")
    if not production_metadata_config_present():
        missing.append("metadata_config_missing")
    if not rbac_ok:
        missing.append("rbac")
    if not tenant_ok:
        missing.append("tenant")
    if not audit_ok:
        missing.append("audit")
    if not customer_policy_ok:
        missing.append("customer_data_policy")
    if not login_live:
        missing.append("login_not_live")

    metadata_validation_attempted = False
    metadata_writes_allowed = False
    write_result = None

    # Never unlock production writes in Gate 25 Mode A / without full gates
    if (
        t.get("approval_valid")
        and t.get("metadata_approved")
        and production_metadata_config_present()
        and t.get("approval_scope")
        not in {"dry_run_only", "none", "invalid", "expired", "revoked"}
    ):
        metadata_validation_attempted = True
        # Still block writes unless secondary confirmation + config + flags —
        # Gate 25 keeps writes false without full production path
        metadata_writes_allowed = False
        missing.append("secondary_confirmation_or_live_path_incomplete")
    else:
        if attempt_write:
            # Call adapter to prove block path
            write_result = production_metadata_write_attempt(
                organization_profile_id="org_demo",
                approval=None,
            )
            metadata_validation_attempted = True
            if write_result.get("status") != "blocked":
                # Force honesty: Mode A must not allow
                metadata_writes_allowed = False

    # Object storage cannot unlock from metadata-only
    object_unlocked = bool(
        t.get("object_storage_approved")
        and t.get("approval_scope")
        in {"object_storage", "controlled_pilot", "production_rollout"}
    )
    if t.get("approval_scope") == "metadata_only":
        object_unlocked = False
        missing.append("metadata_only_cannot_unlock_object_storage")

    # Approval alone cannot unlock customer persistence
    production_storage_claimed = False
    customer_persistence_claimed = False
    if not (
        t.get("customer_persistence_approved")
        and login_live
        and customer_policy_ok
        and rbac_ok
        and tenant_ok
        and audit_ok
        and metadata_writes_allowed
        and object_unlocked
    ):
        customer_persistence_claimed = False
        if t.get("customer_persistence_approved") and not login_live:
            missing.append("approval_alone_cannot_unlock_customer_persistence")

    _emit_audit(
        "metadata_live_path_validation",
        {
            "approval_scope": t.get("approval_scope"),
            "metadata_writes_allowed": metadata_writes_allowed,
            "production_storage_claimed": production_storage_claimed,
        },
    )

    mode = "A"
    if (
        t.get("approval_valid")
        and production_metadata_config_present()
        and t.get("metadata_approved")
    ):
        mode = "B_eligible_incomplete"  # still not Mode B live without full path
    if not t.get("approval_present"):
        mode = "A"

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "mode": mode,
            "storage_approval_ingest_exists": True,
            "approval_token_present": bool(t.get("approval_present")),
            "approval_valid": bool(t.get("approval_valid")),
            "approval_scope": resolve_approval_scope(t),
            "metadata_approved": bool(t.get("metadata_approved")),
            "object_storage_approved": bool(t.get("object_storage_approved")),
            "customer_persistence_approved": bool(
                t.get("customer_persistence_approved")
            ),
            "controlled_pilot_approved": bool(t.get("controlled_pilot_approved")),
            "production_rollout_approved": bool(t.get("production_rollout_approved")),
            "metadata_config_present": production_metadata_config_present(),
            "metadata_validation_attempted": metadata_validation_attempted,
            "metadata_writes_allowed": metadata_writes_allowed,
            "object_storage_unlocked": False,  # Block 55 does not unlock object path
            "production_storage_claimed": production_storage_claimed,
            "customer_persistence_claimed": customer_persistence_claimed,
            "controlled_customer_pilot_status": "NO_GO",
            "production_rollout_status": "NO_GO",
            "login_live_claimed": False,
            "prompt_alone_is_not_approval": True,
            "fake_upload_ui": False,
            "missing_gates": missing,
            "next_owner_action": (
                "Mayhem places repo-safe approval JSON + metadata config out-of-band; "
                "re-run Gate 25 Mode B validators (no secrets in repo)"
            ),
            "token": t,
            "ingest": {
                "ingest_status": ingest.get("ingest_status"),
                "owner_storage_approval_present": ingest.get(
                    "owner_storage_approval_present"
                ),
            },
            "write_probe": write_result,
            "human_review_required": True,
        }
    )


def resolve_production_storage_claim(result: dict[str, Any]) -> dict[str, Any]:
    return _json_safe(
        {
            "production_storage_claimed": False,
            "reason": "all_gates_required",
            "missing_gates": result.get("missing_gates") or [],
        }
    )


def resolve_customer_persistence_claim(result: dict[str, Any]) -> dict[str, Any]:
    return _json_safe(
        {
            "customer_persistence_claimed": False,
            "reason": "policy_auth_storage_tenant_audit_required",
            "missing_gates": result.get("missing_gates") or [],
        }
    )


def storage_approval_metadata_invariant_failures(result: dict[str, Any]) -> list[str]:
    fails: list[str] = []
    for key in (
        "production_storage_claimed",
        "customer_persistence_claimed",
        "metadata_writes_allowed",
        "login_live_claimed",
        "fake_upload_ui",
    ):
        if result.get(key) is True:
            fails.append(key)
    if result.get("controlled_customer_pilot_status") == "GO":
        fails.append("pilot_go")
    return fails


def get_storage_approval_metadata_audit() -> list[dict[str, Any]]:
    return list(_AUDIT)


def clear_storage_approval_metadata_audit_for_tests() -> None:
    _AUDIT.clear()
