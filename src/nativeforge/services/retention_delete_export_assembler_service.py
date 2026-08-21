"""Block 52 assembler: retention/delete/export surface."""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services.retention_delete_export_service import (
    resolve_retention_delete_export,
    retention_delete_export_invariant_failures,
)

SCHEMA_VERSION = "nf_retention_delete_export_assembler_v1"
DOC = "docs/operations/248_RETENTION_DELETE_EXPORT_GATE23.md"


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def build_retention_delete_export_demo_surface() -> dict[str, Any]:
    resolved = resolve_retention_delete_export(archived_or_deleted=True)
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "campaign_block": 52,
            "title": "Retention / delete / export validation + audit linkage",
            "docs": [DOC],
            "retention_policy_contract": True,
            "deletion_request_contract": True,
            "export_request_contract": True,
            "retention_statuses": resolved.get("retention_statuses"),
            "deletion_statuses": resolved.get("deletion_statuses"),
            "export_statuses": resolved.get("export_statuses"),
            "local_dev_delete_behavior": resolved.get("local_dev_delete_behavior"),
            "production_delete_behavior": resolved.get("production_delete_behavior"),
            "production_export_behavior": resolved.get("production_export_behavior"),
            "legal_hold_behavior": resolved.get("legal_hold_behavior"),
            "audit_linkage": True,
            "production_delete_status": (resolved.get("deletion") or {}).get(
                "deletion_status"
            ),
            "export_status": (resolved.get("export") or {}).get("export_status"),
            "final_export_claimed": False,
            "customer_data_persistence_claimed": False,
            "legal_compliance_claimed": False,
            "production_storage_claimed": False,
            "login_live_claimed": False,
            "controlled_customer_pilot_status": "NO_GO",
            "production_rollout_status": "NO_GO",
            "fake_production_export_ui": False,
            "buyer_summary": [
                "Retention/delete/export resolver exists with audited requests",
                "Production delete/export blocked without policy/config/authority/review",
                "Legal hold unsupported blocks legal compliance claim",
                "Archived/deleted evidence cannot unlock package; final export remains false",
            ],
            "next_safe_actions": [
                resolved.get("next_safe_action"),
                "No UI implying production export/delete/customer persistence is live",
            ],
            "human_review_required": True,
            "resolved": resolved,
        }
    )


def retention_delete_export_demo_surface_invariant_failures(
    surface: dict[str, Any],
) -> list[str]:
    fails: list[str] = []
    for key in (
        "final_export_claimed",
        "customer_data_persistence_claimed",
        "legal_compliance_claimed",
        "production_storage_claimed",
        "login_live_claimed",
        "fake_production_export_ui",
    ):
        if surface.get(key) is True:
            fails.append(key)
    fails.extend(
        retention_delete_export_invariant_failures(surface.get("resolved") or {})
    )
    return fails
