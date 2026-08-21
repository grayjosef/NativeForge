"""Repo-safe storage owner approval token model — no secrets (Block 44)."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime, timedelta
from typing import Any

SCHEMA_VERSION = "nf_storage_owner_approval_token_v1"


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def make_storage_owner_approval_id(label: str = "none") -> str:
    raw = f"soat::{label}".encode()
    return f"soat_{hashlib.sha256(raw).hexdigest()[:16]}"


def build_storage_owner_approval_token(
    *,
    present: bool = False,
    approved_by: str = "",
    approval_source: str = "none",
    approved_scope: str = "none",
    approved_backend: str = "none",
    approved_environment: str = "local_dev",
    revoked: bool = False,
    expires_hours: int = 0,
    production_storage_approved: bool = False,
    customer_persistence_approved: bool = False,
) -> dict[str, Any]:
    now = datetime.now(UTC)
    if not present:
        return _json_safe(
            {
                "schema_version": SCHEMA_VERSION,
                "storage_owner_approval_id": make_storage_owner_approval_id("absent"),
                "approval_present": False,
                "approved_by": "",
                "approval_source": "none",
                "approved_at": None,
                "approved_scope": "none",
                "approved_backend": "none",
                "approved_environment": approved_environment,
                "approved_actions": [],
                "excluded_actions": [
                    "provision_production",
                    "enable_customer_persistence",
                    "mutate_customer_data",
                ],
                "expires_at": None,
                "revoked": False,
                "stale": False,
                "production_storage_approved": False,
                "customer_persistence_approved": False,
                "requires_secondary_confirmation": True,
                "approval_alone_does_not_validate": True,
                "human_review_required": True,
            }
        )

    expires_at = (
        (now + timedelta(hours=expires_hours)).isoformat().replace("+00:00", "Z")
        if expires_hours > 0
        else None
    )
    stale = False
    if expires_at:
        # present and not expired
        stale = False
    if revoked:
        production_storage_approved = False
        customer_persistence_approved = False

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "storage_owner_approval_id": make_storage_owner_approval_id(
                f"{approved_by}:{approved_scope}"
            ),
            "approval_present": True,
            "approved_by": approved_by or "owner",
            "approval_source": approval_source,
            "approved_at": now.isoformat().replace("+00:00", "Z"),
            "approved_scope": approved_scope,
            "approved_backend": approved_backend,
            "approved_environment": approved_environment,
            "approved_actions": ["dry_run_provisioning_review"],
            "excluded_actions": [
                "mutate_customer_data",
                "enable_customer_persistence_without_validation",
            ],
            "expires_at": expires_at,
            "revoked": bool(revoked),
            "stale": stale,
            "production_storage_approved": bool(
                production_storage_approved and not revoked and not stale
            ),
            "customer_persistence_approved": bool(
                customer_persistence_approved and not revoked and not stale
            ),
            "requires_secondary_confirmation": True,
            "approval_alone_does_not_validate": True,
            "human_review_required": True,
        }
    )


def storage_owner_approval_token_invariant_failures(
    token: dict[str, Any],
) -> list[str]:
    fails: list[str] = []
    # Mode A default token must not claim production/customer approval
    if not token.get("approval_present"):
        for key in (
            "production_storage_approved",
            "customer_persistence_approved",
        ):
            if token.get(key) is True:
                fails.append(key)
    if token.get("revoked") and token.get("production_storage_approved"):
        fails.append("approved_while_revoked")
    if token.get("stale") and token.get("production_storage_approved"):
        fails.append("approved_while_stale")
    return fails
