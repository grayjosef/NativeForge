"""Evidence metadata model for production metadata adapter (Block 49)."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from typing import Any

SCHEMA_VERSION = "nf_evidence_metadata_model_v1"


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def make_evidence_id(org_id: str, content_hash: str) -> str:
    raw = f"ev::{org_id}::{content_hash}".encode()
    return f"ev_{hashlib.sha256(raw).hexdigest()[:16]}"


def build_evidence_metadata_record(
    *,
    organization_profile_id: str,
    package_workspace_id: str = "ws_default",
    original_filename: str = "evidence.pdf",
    mime_type: str = "application/pdf",
    size_bytes: int = 0,
    content_hash: str = "",
    environment_scope: str = "local_dev",
    customer_data_scope: str = "none",
) -> dict[str, Any]:
    ch = (
        content_hash
        or hashlib.sha256(
            f"{organization_profile_id}:{original_filename}".encode()
        ).hexdigest()
    )
    now = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    eid = make_evidence_id(organization_profile_id, ch)
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "evidence_id": eid,
            "organization_profile_id": organization_profile_id,
            "package_workspace_id": package_workspace_id,
            "source_context": "gate22_metadata_model",
            "original_filename": original_filename,
            "normalized_filename": original_filename.replace(" ", "_").lower(),
            "mime_type": mime_type,
            "size_bytes": int(size_bytes),
            "content_hash": ch,
            "storage_backend": "unassigned",
            "storage_reference": None,
            "object_key": None,
            "uploader_context": "operator_or_fixture",
            "review_status": "pending_review",
            "lifecycle_status": "draft",
            "retention_status": "policy_not_applied",
            "deletion_status": "not_requested",
            "audit_refs": [],
            "created_at": now,
            "updated_at": now,
            "environment_scope": environment_scope,
            "customer_data_scope": customer_data_scope,
        }
    )
