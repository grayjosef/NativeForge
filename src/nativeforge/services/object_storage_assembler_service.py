"""Block 50 assembler: object storage + signed URL surface."""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services.object_storage_signed_url_service import (
    build_object_storage_adapter_status,
    build_org_scoped_object_key,
    generate_signed_upload_url,
    malware_scan_hook,
    object_storage_adapter_invariant_failures,
)

SCHEMA_VERSION = "nf_object_storage_assembler_v1"
DOC = "docs/operations/242_OBJECT_STORAGE_SIGNED_URL_GATE22.md"


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def build_object_storage_demo_surface() -> dict[str, Any]:
    status = build_object_storage_adapter_status()
    key = build_org_scoped_object_key(
        environment_scope="production",
        organization_profile_id="org_demo_a",
        package_workspace_id="ws_demo",
        evidence_id="ev_demo",
        content_hash="abc123",
        normalized_filename="grant_notice.pdf",
    )
    signed = generate_signed_upload_url(
        organization_profile_id="org_demo_a",
        package_workspace_id="ws_demo",
        evidence_id="ev_demo",
        content_hash="abc123",
    )
    scan = malware_scan_hook(object_key=key, satisfied=False)
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "campaign_block": 50,
            "title": "S3-compatible object storage + signed URL path",
            "docs": [DOC],
            "object_storage_adapter": True,
            "production_object_config_present": False,
            "signed_upload_url_path": status.get("signed_upload_url_path"),
            "signed_download_url_path": status.get("signed_download_url_path"),
            "malware_scan_hook": status.get("malware_scan_hook"),
            "malware_scan_status": scan.get("status"),
            "sse_encryption_model": status.get("sse_encryption"),
            "object_key_scoping": status.get("object_key_scoping"),
            "sample_object_key": key,
            "signed_upload_status": signed.get("status"),
            "archive_delete_behavior": status.get("archive_delete_behavior"),
            "production_writes_allowed": False,
            "production_storage_claimed": False,
            "customer_data_persistence_claimed": False,
            "login_live_claimed": False,
            "controlled_customer_pilot_status": "NO_GO",
            "production_rollout_status": "NO_GO",
            "fake_upload_ui_exposed": False,
            "buyer_summary": [
                "Object storage adapter and signed URL path exist behind gates",
                "Malware scan hook required before persistence",
                "Org-scoped object keys prevent cross-org leakage",
                "Production writes and signed URLs blocked without approval/config",
            ],
            "next_safe_actions": [
                status.get("next_safe_action"),
                "No fake production upload UI — claim remains false",
            ],
            "human_review_required": True,
            "adapter_status": status,
        }
    )


def object_storage_demo_surface_invariant_failures(
    surface: dict[str, Any],
) -> list[str]:
    fails: list[str] = []
    for key in (
        "production_object_config_present",
        "production_writes_allowed",
        "production_storage_claimed",
        "customer_data_persistence_claimed",
        "login_live_claimed",
        "fake_upload_ui_exposed",
    ):
        if surface.get(key) is True:
            fails.append(key)
    fails.extend(
        object_storage_adapter_invariant_failures(surface.get("adapter_status") or {})
    )
    return fails
