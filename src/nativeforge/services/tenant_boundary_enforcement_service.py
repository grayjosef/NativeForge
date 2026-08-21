"""Tenant boundary enforcement (Campaign Block 31)."""

from __future__ import annotations

import json
from typing import Any

SCHEMA_VERSION = "nf_tenant_boundary_enforcement_v1"

PROTECTED_OBJECT_TYPES = frozenset(
    {
        "org_profile",
        "evidence_intake",
        "evidence_lifecycle",
        "package_workspace",
        "checklist",
        "binder",
        "forms_attachments_map",
        "draft_workspace",
        "controlled_draft",
        "ai_governance",
        "feedback_report",
        "source_packet",
        "applicant_authority",
        "package_export_preview",
    }
)


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def assert_tenant_access(
    *,
    requesting_org_id: str,
    resource_org_id: str,
    object_type: str,
    action: str,
) -> dict[str, Any]:
    """Deny cross-org access. Operator override not supported in Gate 13."""
    ot = object_type if object_type in PROTECTED_OBJECT_TYPES else "unknown"
    same = requesting_org_id == resource_org_id and bool(requesting_org_id)
    allowed = bool(same)
    denial = None
    if not allowed:
        denial = {
            "event_type": "tenant_boundary_denied",
            "requesting_org_id": requesting_org_id,
            "resource_org_id": resource_org_id,
            "object_type": ot,
            "action": action,
            "reason": "cross_org_access_denied",
            "operator_override_supported": False,
            "environment_scope": "enforcement_model",
        }
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "allowed": allowed,
            "object_type": ot,
            "action": action,
            "denial_audit_event": denial,
            "production_multi_tenant_claimed": False,
        }
    )


def run_tenant_isolation_suite() -> dict[str, Any]:
    org_a = "org_a_demo"
    org_b = "org_b_demo"
    cases = [
        ("evidence_intake", "read"),
        ("evidence_lifecycle", "link"),
        ("applicant_authority", "use"),
        ("package_export_preview", "export"),
        ("feedback_report", "write"),
        ("package_workspace", "read"),
        ("draft_workspace", "read"),
        ("source_packet", "read"),
    ]
    results = []
    fails: list[str] = []
    for ot, action in cases:
        # Same-org allow
        ok = assert_tenant_access(
            requesting_org_id=org_a,
            resource_org_id=org_a,
            object_type=ot,
            action=action,
        )
        if not ok["allowed"]:
            fails.append(f"same_org_denied:{ot}")
        # Cross-org deny
        cross = assert_tenant_access(
            requesting_org_id=org_a,
            resource_org_id=org_b,
            object_type=ot,
            action=action,
        )
        if cross["allowed"]:
            fails.append(f"cross_org_allowed:{ot}")
        if not cross.get("denial_audit_event"):
            fails.append(f"missing_denial_audit:{ot}")
        results.append(
            {
                "object_type": ot,
                "same_ok": ok["allowed"],
                "cross_denied": not cross["allowed"],
            }
        )

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "overall_status": "PASS" if not fails else "FAIL",
            "fails": fails,
            "case_results": results,
            "operator_override_supported": False,
            "production_multi_tenant_claimed": False,
            "tenant_isolation_model_exists": True,
        }
    )


def tenant_isolation_suite_invariant_failures(report: dict[str, Any]) -> list[str]:
    fails: list[str] = []
    if report.get("production_multi_tenant_claimed") is True:
        fails.append("production_multi_tenant_claimed")
    if report.get("operator_override_supported") is True:
        fails.append("operator_override_supported")
    if report.get("overall_status") != "PASS":
        fails.extend([f"iso:{x}" for x in (report.get("fails") or ["fail"])])
    return fails
