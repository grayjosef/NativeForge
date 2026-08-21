"""Block 56 assembler: object storage signed-URL unlock."""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services.gate25_object_storage_unlock_service import (
    object_storage_unlock_invariant_failures,
    run_object_storage_signed_url_unlock,
)

SCHEMA_VERSION = "nf_gate25_object_storage_assembler_v1"
DOC = "docs/operations/261_GATE25_OBJECT_STORAGE_SIGNED_URL_PATH.md"


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def build_object_storage_unlock_demo_surface() -> dict[str, Any]:
    result = run_object_storage_signed_url_unlock()
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "campaign_block": 56,
            "title": "Object storage signed-URL unlock under approval + malware/SSE",
            "docs": [DOC],
            "object_storage_approval_resolver": True,
            "object_config_present": result.get("object_config_present"),
            "signed_upload_url_validator": True,
            "signed_download_url_validator": True,
            "signed_upload_status": result.get("signed_upload_status"),
            "signed_download_status": result.get("signed_download_status"),
            "object_key_policy_status": "enforced",
            "path_traversal_protection": True,
            "sse_encryption_status": (result.get("sse_encryption_gate") or {}).get(
                "configured"
            ),
            "malware_scan_status": (result.get("malware_scan_gate") or {}).get("status"),
            "archive_delete_blocked": (
                result.get("archive_delete_gate") or {}
            ).get("blocked_without_approval"),
            "production_object_writes_allowed": False,
            "signed_urls_live": False,
            "production_storage_claimed": False,
            "customer_persistence_claimed": False,
            "controlled_pilot_storage_ready": False,
            "controlled_customer_pilot_status": "NO_GO",
            "production_rollout_status": "NO_GO",
            "login_live_claimed": False,
            "fake_upload_ui": False,
            "fake_signed_url_ui": False,
            "missing_gates": result.get("missing_gates"),
            "next_owner_action": result.get("next_owner_action"),
            "buyer_summary": [
                "Object storage + signed URL validators exist behind approval gates",
                "Org-scoped keys + path traversal normalization enforced",
                "SSE/malware gates block production persistence until satisfied",
                "Production object writes and signed URLs remain blocked in Mode A",
            ],
            "next_safe_actions": [
                result.get("next_owner_action"),
                "No fake signed URL or upload UI",
            ],
            "human_review_required": True,
            "result": result,
        }
    )


def object_storage_unlock_demo_surface_invariant_failures(
    surface: dict[str, Any],
) -> list[str]:
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
        if surface.get(key) is True:
            fails.append(key)
    fails.extend(object_storage_unlock_invariant_failures(surface.get("result") or {}))
    return fails
