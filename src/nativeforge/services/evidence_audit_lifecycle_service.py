"""Evidence audit events + retention policy + unlock rules (Block 29)."""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import UTC, datetime
from typing import Any

from nativeforge.services.evidence_lifecycle_contract_service import (
    build_evidence_lifecycle_record,
    evidence_lifecycle_invariant_failures,
)

SCHEMA_VERSION = "nf_evidence_audit_lifecycle_v1"

EVENT_TYPES = frozenset(
    {
        "evidence_created",
        "evidence_read",
        "evidence_linked",
        "evidence_review_started",
        "evidence_approved",
        "evidence_rejected",
        "evidence_archived",
        "evidence_delete_requested",
        "evidence_deleted_local_dev",
        "package_unlock_evaluated",
        "export_unlock_evaluated",
        "cross_org_access_denied",
        "invalid_upload_rejected",
    }
)


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def make_audit_event_id(evidence_id: str, event_type: str, nonce: str) -> str:
    raw = f"eae::{evidence_id}::{event_type}::{nonce}".encode()
    return f"eae_{hashlib.sha256(raw).hexdigest()[:16]}"


def build_evidence_audit_event(
    *,
    evidence_intake_id: str,
    organization_profile_id: str,
    event_type: str,
    actor_source: str = "local_dev_operator",
    package_workspace_id: str | None = None,
    previous_state: str | None = None,
    next_state: str | None = None,
    reason: str | None = None,
) -> dict[str, Any]:
    et = event_type if event_type in EVENT_TYPES else "invalid_upload_rejected"
    nonce = uuid.uuid4().hex[:8]
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "event_id": make_audit_event_id(evidence_intake_id, et, nonce),
            "actor_source": actor_source,
            "organization_profile_id": organization_profile_id,
            "package_workspace_id": package_workspace_id,
            "evidence_intake_id": evidence_intake_id,
            "event_type": et,
            "timestamp": datetime.now(UTC).isoformat(),
            "previous_state": previous_state,
            "next_state": next_state,
            "reason": reason,
            "data_scope": "organization_only",
            "environment_scope": "local_dev_only",
            "production_audit_claimed": False,
        }
    )


def build_retention_deletion_policy_model(
    *,
    organization_profile_id: str,
) -> dict[str, Any]:
    return _json_safe(
        {
            "schema_version": "nf_evidence_retention_policy_v1",
            "organization_profile_id": organization_profile_id,
            "retention_duration": "unknown_unless_policy_set",
            "customer_deletion_request_flow": "modeled_operator_approval_required",
            "legal_hold": "unsupported_unless_implemented",
            "archive_vs_delete": "archive_soft_delete_then_local_dev_delete_if_approved",
            "local_dev_delete_supported": True,
            "production_deletion_claimed": False,
            "export_delete_data_sovereignty_requirements": [
                "org-scoped isolation",
                "operator approval before delete",
                "audit trail retained",
            ],
            "operator_approval_required": True,
            "legal_compliance_claimed": False,
            "production_policy_validated": False,
        }
    )


def evaluate_package_export_unlock(
    *,
    lifecycle: dict[str, Any],
    qa_passed: bool = False,
    authority_submission_ok: bool = False,
    human_review_complete: bool = False,
) -> dict[str, Any]:
    """Export unlock requires approved evidence + QA + authority + human review."""
    package_ok = lifecycle.get("package_unlock_status") == "unlocked_for_requirement"
    export_unlocked = bool(
        package_ok and qa_passed and authority_submission_ok and human_review_complete
    )
    # Gate 12: authority_submission_ok should never be true from current authority model
    return _json_safe(
        {
            "package_unlock_status": lifecycle.get("package_unlock_status"),
            "export_unlock_status": "unlocked" if export_unlocked else "locked",
            "submission_unlock_status": False,
            "qa_passed": bool(qa_passed),
            "authority_submission_ok": bool(authority_submission_ok),
            "human_review_complete": bool(human_review_complete),
            "blockers": []
            if export_unlocked
            else [
                b
                for b, ok in [
                    ("evidence_not_approved_for_package", not package_ok),
                    ("qa_not_passed", not qa_passed),
                    ("authority_not_ok", not authority_submission_ok),
                    ("human_review_incomplete", not human_review_complete),
                ]
                if ok
            ],
            "submission_ready_claimed": False,
            "final_export_claimed": False,
        }
    )


def run_evidence_lifecycle_demo_flow(
    *,
    organization_profile_id: str = "sc_pilot_catawba_indian_nation",
    evidence_label: str = "gate12_lifecycle_demo",
) -> dict[str, Any]:
    """Produce lifecycle transitions + audit events in local/dev model."""
    ei_id = f"ei_demo_{hashlib.sha256(evidence_label.encode()).hexdigest()[:12]}"
    events: list[dict[str, Any]] = []
    events.append(
        build_evidence_audit_event(
            evidence_intake_id=ei_id,
            organization_profile_id=organization_profile_id,
            event_type="evidence_created",
            previous_state=None,
            next_state="created",
        )
    )
    events.append(
        build_evidence_audit_event(
            evidence_intake_id=ei_id,
            organization_profile_id=organization_profile_id,
            event_type="evidence_linked",
            previous_state="created",
            next_state="linked",
        )
    )
    events.append(
        build_evidence_audit_event(
            evidence_intake_id=ei_id,
            organization_profile_id=organization_profile_id,
            event_type="evidence_review_started",
            previous_state="linked",
            next_state="under_review",
        )
    )
    # Reject path then archive
    rejected = build_evidence_lifecycle_record(
        evidence_intake_id=ei_id,
        organization_profile_id=organization_profile_id,
        package_workspace_id="pkg_demo_sc",
        lifecycle_status="rejected",
        review_status="rejected",
    )
    events.append(
        build_evidence_audit_event(
            evidence_intake_id=ei_id,
            organization_profile_id=organization_profile_id,
            event_type="evidence_rejected",
            previous_state="under_review",
            next_state="rejected",
            reason="demo_reject_path",
        )
    )
    events.append(
        build_evidence_audit_event(
            evidence_intake_id=ei_id,
            organization_profile_id=organization_profile_id,
            event_type="package_unlock_evaluated",
            reason=f"status={rejected['package_unlock_status']}",
            next_state=rejected["package_unlock_status"],
        )
    )

    # Approve path on alternate id
    ei2 = f"{ei_id}_approved"
    approved = build_evidence_lifecycle_record(
        evidence_intake_id=ei2,
        organization_profile_id=organization_profile_id,
        package_workspace_id="pkg_demo_sc",
        lifecycle_status="approved",
        review_status="approved",
        retention_status="retain_active",
    )
    events.append(
        build_evidence_audit_event(
            evidence_intake_id=ei2,
            organization_profile_id=organization_profile_id,
            event_type="evidence_approved",
            next_state="approved",
        )
    )
    unlock = evaluate_package_export_unlock(
        lifecycle=approved,
        qa_passed=True,
        authority_submission_ok=False,  # authority model still blocks submit
        human_review_complete=True,
    )
    events.append(
        build_evidence_audit_event(
            evidence_intake_id=ei2,
            organization_profile_id=organization_profile_id,
            event_type="export_unlock_evaluated",
            reason=f"export={unlock['export_unlock_status']}",
            next_state=unlock["export_unlock_status"],
        )
    )
    # Cross-org deny
    events.append(
        build_evidence_audit_event(
            evidence_intake_id=ei2,
            organization_profile_id="other_org_denied",
            event_type="cross_org_access_denied",
            reason="cross_org_read_blocked",
        )
    )
    policy = build_retention_deletion_policy_model(
        organization_profile_id=organization_profile_id
    )
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "rejected_lifecycle": rejected,
            "approved_lifecycle": approved,
            "export_unlock_evaluation": unlock,
            "retention_policy": policy,
            "audit_events": events,
            "audit_event_count": len(events),
            "submission_unlock_status": False,
            "production_policy_validated": False,
            "legal_compliance_claimed": False,
        }
    )


def evidence_audit_flow_invariant_failures(flow: dict[str, Any]) -> list[str]:
    fails: list[str] = []
    if not (flow.get("audit_events") or []):
        fails.append("no_audit_events")
    if flow.get("submission_unlock_status") is not False:
        fails.append("submission_unlock")
    if flow.get("production_policy_validated") is True:
        fails.append("production_policy_validated")
    if flow.get("legal_compliance_claimed") is True:
        fails.append("legal_compliance_claimed")
    fails.extend(
        evidence_lifecycle_invariant_failures(flow.get("rejected_lifecycle") or {})
    )
    fails.extend(
        evidence_lifecycle_invariant_failures(flow.get("approved_lifecycle") or {})
    )
    unlock = flow.get("export_unlock_evaluation") or {}
    if unlock.get("submission_unlock_status") is not False:
        fails.append("export_eval_submission_unlock")
    if unlock.get("export_unlock_status") == "unlocked":
        fails.append("export_unlocked_without_authority")
    policy = flow.get("retention_policy") or {}
    if policy.get("production_deletion_claimed") is True:
        fails.append("production_deletion_claimed")
    if policy.get("legal_compliance_claimed") is True:
        fails.append("policy_legal_compliance")
    return fails
