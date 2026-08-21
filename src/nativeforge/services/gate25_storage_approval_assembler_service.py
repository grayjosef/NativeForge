"""Block 55 assembler: storage approval + metadata live path."""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services.gate25_storage_approval_metadata_service import (
    resolve_customer_persistence_claim,
    resolve_production_storage_claim,
    storage_approval_metadata_invariant_failures,
    validate_production_metadata_live_path,
)

SCHEMA_VERSION = "nf_gate25_storage_approval_assembler_v1"
DOC = "docs/operations/259_GATE25_STORAGE_APPROVAL_INGEST.md"


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def build_storage_approval_metadata_demo_surface() -> dict[str, Any]:
    result = validate_production_metadata_live_path()
    prod = resolve_production_storage_claim(result)
    persist = resolve_customer_persistence_claim(result)
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "campaign_block": 55,
            "title": "Storage approval ingest / production metadata live path",
            "docs": [DOC, "docs/operations/260_GATE25_PRODUCTION_METADATA_LIVE_PATH.md"],
            "storage_approval_ingest_service": True,
            "mode": result.get("mode"),
            "approval_token_present": result.get("approval_token_present"),
            "approval_valid": result.get("approval_valid"),
            "approval_scope": result.get("approval_scope"),
            "metadata_approved": result.get("metadata_approved"),
            "object_storage_approved": result.get("object_storage_approved"),
            "customer_persistence_approved": result.get("customer_persistence_approved"),
            "controlled_pilot_approved": result.get("controlled_pilot_approved"),
            "metadata_config_present": result.get("metadata_config_present"),
            "metadata_validation_attempted": result.get("metadata_validation_attempted"),
            "metadata_writes_allowed": False,
            "production_storage_claimed": False,
            "customer_persistence_claimed": False,
            "controlled_customer_pilot_status": "NO_GO",
            "production_rollout_status": "NO_GO",
            "login_live_claimed": False,
            "prompt_alone_is_not_approval": True,
            "fake_upload_ui": False,
            "missing_gates": result.get("missing_gates"),
            "next_owner_action": result.get("next_owner_action"),
            "buyer_summary": [
                "Storage approval ingest exists; prompt text is not approval",
                "Metadata live path validates scopes (dry-run/metadata-only/object/pilot)",
                "Mode A: metadata writes and production storage remain blocked",
                "Approval alone cannot unlock customer persistence",
            ],
            "next_safe_actions": [
                result.get("next_owner_action"),
                "No fake upload UI",
            ],
            "human_review_required": True,
            "result": result,
            "production_storage_resolver": prod,
            "customer_persistence_resolver": persist,
        }
    )


def storage_approval_metadata_demo_surface_invariant_failures(
    surface: dict[str, Any],
) -> list[str]:
    fails: list[str] = []
    for key in (
        "production_storage_claimed",
        "customer_persistence_claimed",
        "metadata_writes_allowed",
        "login_live_claimed",
        "fake_upload_ui",
    ):
        if surface.get(key) is True:
            fails.append(key)
    fails.extend(
        storage_approval_metadata_invariant_failures(surface.get("result") or {})
    )
    return fails
