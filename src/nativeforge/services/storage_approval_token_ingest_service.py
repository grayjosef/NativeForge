"""Block 48: Storage approval token ingest — prompt alone is not approval."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from nativeforge.services.storage_owner_approval_token_service import (
    build_storage_owner_approval_token,
)

SCHEMA_VERSION = "nf_storage_approval_token_ingest_v1"

# Explicit owner file path — must exist AND be valid JSON token fields (no secrets)
DEFAULT_APPROVAL_PATH = Path("artifacts/owner_storage_approval_token.json")
ENV_APPROVAL_PATH = "NF_STORAGE_OWNER_APPROVAL_TOKEN_PATH"


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def ingest_storage_owner_approval_token(
    *,
    approval_path: Path | None = None,
) -> dict[str, Any]:
    """Ingest repo-safe approval only from explicit file/env path — never from prompt."""
    path = approval_path
    if path is None:
        env_path = os.environ.get(ENV_APPROVAL_PATH, "").strip()
        path = Path(env_path) if env_path else DEFAULT_APPROVAL_PATH

    if not path.exists():
        token = build_storage_owner_approval_token(present=False)
        return _json_safe(
            {
                "schema_version": SCHEMA_VERSION,
                "ingest_status": "ABSENT",
                "approval_source_path": str(path),
                "owner_storage_approval_present": False,
                "approval_valid": False,
                "token": token,
                "prompt_alone_is_not_approval": True,
                "production_storage_claimed": False,
                "customer_data_persistence_claimed": False,
                "reason": "No owner approval token file present",
                "next_safe_action": (
                    f"Mayhem places repo-safe approval JSON at {path} "
                    f"(or set {ENV_APPROVAL_PATH}); re-run Block 48 smoke"
                ),
                "human_review_required": True,
            }
        )

    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return _json_safe(
            {
                "schema_version": SCHEMA_VERSION,
                "ingest_status": "INVALID",
                "approval_source_path": str(path),
                "owner_storage_approval_present": False,
                "approval_valid": False,
                "token": build_storage_owner_approval_token(present=False),
                "prompt_alone_is_not_approval": True,
                "production_storage_claimed": False,
                "customer_data_persistence_claimed": False,
                "reason": f"Approval file unreadable: {type(exc).__name__}",
                "next_safe_action": "Fix approval JSON (no secrets) and re-ingest",
                "human_review_required": True,
            }
        )

    # Never accept secret-looking keys
    banned = {"client_secret", "password", "api_key", "OIDC_CLIENT_SECRET"}
    if any(k in raw for k in banned):
        return _json_safe(
            {
                "schema_version": SCHEMA_VERSION,
                "ingest_status": "REJECTED_SECRETS",
                "approval_source_path": str(path),
                "owner_storage_approval_present": False,
                "approval_valid": False,
                "token": build_storage_owner_approval_token(present=False),
                "prompt_alone_is_not_approval": True,
                "production_storage_claimed": False,
                "customer_data_persistence_claimed": False,
                "reason": "Approval file contained forbidden secret-like keys",
                "next_safe_action": "Remove secrets from approval token file",
                "human_review_required": True,
            }
        )

    revoked = bool(raw.get("revoked"))
    present = bool(raw.get("approval_present", True))
    prod_approved = bool(raw.get("production_storage_approved")) and not revoked
    cust_approved = bool(raw.get("customer_persistence_approved")) and not revoked

    token = build_storage_owner_approval_token(
        present=present,
        approved_by=str(raw.get("approved_by") or "owner"),
        approval_source=str(raw.get("approval_source") or "owner_file"),
        approved_scope=str(raw.get("approved_scope") or "production_storage_review"),
        approved_backend=str(raw.get("approved_backend") or "managed_postgres_s3"),
        approved_environment=str(raw.get("approved_environment") or "production"),
        revoked=revoked,
        expires_hours=int(raw.get("expires_hours") or 0),
        production_storage_approved=prod_approved,
        customer_persistence_approved=cust_approved,
    )

    approval_valid = bool(
        token.get("approval_present")
        and token.get("production_storage_approved")
        and not token.get("revoked")
        and not token.get("stale")
    )

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "ingest_status": "INGESTED" if present else "ABSENT",
            "approval_source_path": str(path),
            "owner_storage_approval_present": bool(token.get("approval_present")),
            "approval_valid": approval_valid,
            "token": token,
            "prompt_alone_is_not_approval": True,
            # Approval alone never claims production storage validated
            "production_storage_claimed": False,
            "customer_data_persistence_claimed": False,
            "approval_alone_does_not_validate": True,
            "reason": (
                "Approval ingested; provisioning validation still required"
                if approval_valid
                else "Approval absent, revoked, stale, or incomplete"
            ),
            "next_safe_action": (
                "Run provisioning validation with config present; keep claims false until validated"
                if approval_valid
                else "Provide valid repo-safe approval token file"
            ),
            "human_review_required": True,
        }
    )


def storage_approval_token_ingest_invariant_failures(
    result: dict[str, Any],
) -> list[str]:
    fails: list[str] = []
    for key in (
        "production_storage_claimed",
        "customer_data_persistence_claimed",
    ):
        if result.get(key) is True:
            fails.append(key)
    if not result.get("prompt_alone_is_not_approval"):
        fails.append("prompt_alone_flag_missing")
    return fails
