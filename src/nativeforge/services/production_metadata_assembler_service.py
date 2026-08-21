"""Block 49 assembler: production metadata adapter surface."""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services.evidence_metadata_model_service import (
    build_evidence_metadata_record,
)
from nativeforge.services.production_metadata_adapter_service import (
    build_production_metadata_adapter_status,
    production_metadata_adapter_invariant_failures,
    production_metadata_write_attempt,
)

SCHEMA_VERSION = "nf_production_metadata_assembler_v1"
DOC = "docs/operations/241_PRODUCTION_METADATA_ADAPTER_GATE22.md"


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def build_production_metadata_demo_surface() -> dict[str, Any]:
    status = build_production_metadata_adapter_status()
    sample = build_evidence_metadata_record(
        organization_profile_id="org_demo_a",
        package_workspace_id="ws_demo",
    )
    blocked = production_metadata_write_attempt(organization_profile_id="org_demo_a")
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "campaign_block": 49,
            "title": "Production metadata adapter (behind flags)",
            "docs": [DOC],
            "metadata_adapter_interface": True,
            "local_dev_metadata_behavior": "allowed_validated_persistent",
            "production_metadata_config_present": bool(
                status.get("production_metadata_config_present")
            ),
            "owner_approval_present": False,
            "production_metadata_writes_allowed": False,
            "evidence_metadata_model": sample,
            "tenant_org_scoping": True,
            "audit_linkage": True,
            "retention_delete_linkage": True,
            "production_write_attempt_status": blocked.get("status"),
            "production_storage_claimed": False,
            "customer_data_persistence_claimed": False,
            "login_live_claimed": False,
            "controlled_customer_pilot_status": "NO_GO",
            "production_rollout_status": "NO_GO",
            "missing_gates": blocked.get("reasons"),
            "buyer_summary": [
                "Managed Postgres metadata adapter interface exists behind flags",
                "Local/dev metadata writes remain allowed",
                "Production metadata writes blocked without approval/config",
                "Org-scoped access prevents cross-org metadata reads",
            ],
            "next_safe_actions": [
                status.get("next_safe_action"),
                "Do not enable production_storage_enabled until validated",
            ],
            "human_review_required": True,
            "adapter_status": status,
        }
    )


def production_metadata_demo_surface_invariant_failures(
    surface: dict[str, Any],
) -> list[str]:
    fails: list[str] = []
    for key in (
        "owner_approval_present",
        "production_metadata_writes_allowed",
        "production_storage_claimed",
        "customer_data_persistence_claimed",
        "login_live_claimed",
    ):
        if surface.get(key) is True:
            fails.append(key)
    fails.extend(
        production_metadata_adapter_invariant_failures(
            surface.get("adapter_status") or {}
        )
    )
    return fails
