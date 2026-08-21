"""Evidence lifecycle demo assembler (Campaign Block 29)."""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services.evidence_audit_lifecycle_service import (
    evidence_audit_flow_invariant_failures,
    run_evidence_lifecycle_demo_flow,
)

SCHEMA_VERSION = "nf_evidence_lifecycle_assembler_v1"


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def build_evidence_lifecycle_demo_surface() -> dict[str, Any]:
    flow = run_evidence_lifecycle_demo_flow()
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "campaign_block": 29,
            "title": "Evidence lifecycle / retention / audit",
            "flow": flow,
            "buyer_summary": [
                "Evidence lifecycle model covers create→link→review→approve/reject→archive/delete",
                "Audit events are generated in local/dev scope",
                "Package unlock requires approval; export still blocked without authority",
                "Submission unlock remains false; production retention/legal compliance not claimed",
            ],
            "lifecycle_statuses_supported": [
                "created",
                "linked",
                "under_review",
                "approved",
                "rejected",
                "archived",
                "delete_requested",
                "deleted_local_dev",
            ],
            "audit_event_count": flow.get("audit_event_count"),
            "package_unlock_behavior": "approved_may_satisfy_mapped_requirement_only",
            "export_unlock_behavior": "requires_approved_plus_qa_authority_human_review",
            "submission_unlock_status": False,
            "production_policy_validated": False,
            "legal_compliance_claimed": False,
            "production_storage_claimed": False,
            "customer_data_persistence_claimed": False,
            "submission_ready_claimed": False,
            "final_export_claimed": False,
        }
    )


def evidence_lifecycle_demo_surface_invariant_failures(
    surface: dict[str, Any],
) -> list[str]:
    fails: list[str] = []
    for key in (
        "submission_unlock_status",
        "production_policy_validated",
        "legal_compliance_claimed",
        "production_storage_claimed",
        "customer_data_persistence_claimed",
        "submission_ready_claimed",
        "final_export_claimed",
    ):
        if surface.get(key) is True:
            fails.append(key)
    fails.extend(evidence_audit_flow_invariant_failures(surface.get("flow") or {}))
    return fails
