"""Production storage backend recommendation (Block 38)."""

from __future__ import annotations

import json
from typing import Any

SCHEMA_VERSION = "nf_production_storage_backend_recommendation_v1"
DOC_ARTIFACT = "docs/operations/205_PRODUCTION_STORAGE_BACKEND_RECOMMENDATION.md"


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def build_production_storage_backend_recommendation() -> dict[str, Any]:
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "artifact": DOC_ARTIFACT,
            "recommended_backend": {
                "metadata_db": "managed Postgres (encrypted at rest)",
                "object_storage": "S3-compatible managed object store with SSE",
                "access_pattern": "signed URLs short TTL + RBAC/tenant checks",
                "malware_scanning": "required dependency before customer uploads",
                "encryption_at_rest": "required",
                "backup_restore": "automated snapshots + tested restore drill",
                "retention_delete": "policy-linked lifecycle + soft-delete audit",
                "audit_event_linkage": "required (nf_unified_audit_event_v1)",
            },
            "rejected_options": [
                {
                    "option": "local_sqlite_for_production",
                    "reason": "not multi-tenant durable customer storage",
                },
                {
                    "option": "unencrypted_local_disk_blobs",
                    "reason": "fails customer data policy baseline",
                },
                {
                    "option": "shared_cross_org_bucket_without_prefix_isolation",
                    "reason": "tenant isolation risk",
                },
            ],
            "approval_required": True,
            "implementation_sequence": [
                "Owner approves backend + malware + retention baseline",
                "Provision metadata DB + object store (non-prod first)",
                "Wire signed URL + RBAC/tenant enforcement",
                "Validate backup/restore + delete path",
                "Staged pilot storage only after auth live path ready",
            ],
            "rollback_considerations": [
                "Keep local/dev adapter for demo",
                "Feature-flag production adapter OFF until validated",
                "Do not migrate customer data until policy approved",
            ],
            "claim_boundary": {
                "production_storage_approved": False,
                "production_storage_validated": False,
                "customer_data_persistence_claimed": False,
                "local_dev_storage_validated": True,
            },
            "sunday_feasibility": "owner_decision_this_weekend_implementation_conditional",
            "production_suitability": "recommended_when_approved",
            "cost_complexity": "medium",
            "human_review_required": True,
        }
    )


def production_storage_backend_recommendation_invariant_failures(
    rec: dict[str, Any],
) -> list[str]:
    fails: list[str] = []
    claims = rec.get("claim_boundary") or {}
    for key in (
        "production_storage_approved",
        "production_storage_validated",
        "customer_data_persistence_claimed",
    ):
        if claims.get(key) is True:
            fails.append(key)
    if rec.get("approval_required") is not True:
        fails.append("approval_not_required")
    return fails
