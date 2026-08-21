"""Customer pilot auth scaffolding assembler (Campaign Block 24)."""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services.customer_access_boundary_contract_service import (
    assert_no_cross_org_access,
    build_customer_access_boundary_contract,
    customer_access_boundary_invariant_failures,
)
from nativeforge.services.evidence_intake_assembler_service import (
    build_evidence_intake_demo_surface,
)
from nativeforge.services.multi_org_pilot_assembler_service import (
    DEFAULT_COHORT_ORG_IDS,
    build_multi_org_pilot_demo_surface,
)

SCHEMA_VERSION = "nf_customer_pilot_auth_assembler_v1"


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def build_customer_pilot_readiness_checklist() -> dict[str, Any]:
    return {
        "auth_mode": "fixture_scoped",
        "login_live": False,
        "external_pilot_enabled": False,
        "org_scoped_data_ready": True,  # fixture model ready, not production
        "feedback_report_safe": True,
        "upload_persistence_ready": False,
        "export_ready": False,
        "collaboration_enabled": False,
        "source_freshness_ready": False,
        "pen_test_passed": False,
        "required_before_controlled_customer_pilot": [
            "Production or customer-scoped durable storage (local/dev only is not enough)",
            "External pilot auth path enabled and validated (login still gated)",
            "Org-scoped access enforcement beyond fixture model",
            "Pen-test / SCA as applicable (not claimed passed)",
        ],
        "required_before_production": [
            "Production auth + multi-tenant isolation validated",
            "External pen-test passed (do not claim until true)",
            "Upload persistence validated",
            "Live source activation approval",
        ],
        "controlled_customer_pilot_status": "NO_GO",
        "production_status": "NO_GO",
    }


def build_customer_pilot_auth_demo_surface() -> dict[str, Any]:
    multi = build_multi_org_pilot_demo_surface()
    evidence = build_evidence_intake_demo_surface(max_orgs=4)
    cohort_id = str((multi.get("cohort") or {}).get("pilot_cohort_id") or "cohort_demo")
    org_states = multi.get("organizations") or []
    evidence_by_org = {
        w.get("organization_profile_id"): w for w in (evidence.get("workspaces") or [])
    }

    boundaries: list[dict[str, Any]] = []
    for state in org_states[:4]:
        oid = str(state.get("organization_profile_id") or "")
        ews = evidence_by_org.get(oid) or {}
        evidence_ids = [
            str(r.get("evidence_intake_id"))
            for r in (ews.get("records") or [])
            if r.get("evidence_intake_id")
        ]
        boundary = build_customer_access_boundary_contract(
            organization_profile_id=oid,
            pilot_cohort_id=cohort_id,
            auth_mode="fixture_scoped",
            allowed_package_ids=list(state.get("package_workspace_ids") or []),
            allowed_evidence_ids=evidence_ids,
            allowed_feedback_context_ids=[str(state.get("feedback_context_id") or "")],
        )
        boundaries.append(boundary)

    # Cross-org isolation check across first two orgs
    isolation_fails: list[str] = []
    if len(boundaries) >= 2:
        a, b = boundaries[0], boundaries[1]
        isolation_fails.extend(
            assert_no_cross_org_access(
                a,
                other_org_id=str(b.get("organization_profile_id")),
                other_package_ids=list(b.get("allowed_package_ids") or []),
                other_evidence_ids=list(b.get("allowed_evidence_ids") or []),
                other_feedback_ids=list(b.get("allowed_feedback_context_ids") or []),
            )
        )
        isolation_fails.extend(
            assert_no_cross_org_access(
                b,
                other_org_id=str(a.get("organization_profile_id")),
                other_package_ids=list(a.get("allowed_package_ids") or []),
                other_evidence_ids=list(a.get("allowed_evidence_ids") or []),
                other_feedback_ids=list(a.get("allowed_feedback_context_ids") or []),
            )
        )

    checklist = build_customer_pilot_readiness_checklist()
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "campaign_block": 24,
            "title": "Controlled customer pilot auth scaffolding",
            "boundaries": boundaries,
            "boundary_count": len(boundaries),
            "cohort_org_ids": list(DEFAULT_COHORT_ORG_IDS),
            "isolation_check_fails": isolation_fails,
            "readiness_checklist": checklist,
            "buyer_summary": [
                "Access boundary model scopes orgs to their own package/evidence/feedback IDs",
                "Login is not live; production auth and multi-tenant isolation not claimed",
                "Controlled customer pilot remains NO_GO until storage + auth conditions met",
                "Collaboration and final export remain OFF in customer scope",
            ],
            "login_live_claimed": False,
            "production_auth_claimed": False,
            "rbac_enforced_claimed": False,
            "production_multi_tenant_claimed": False,
            "customer_data_isolation_claimed": False,
            "controlled_customer_pilot_status": checklist[
                "controlled_customer_pilot_status"
            ],
            "blockers": list(checklist["required_before_controlled_customer_pilot"]),
            "next_safe_actions": [
                "Keep demo_operator_view / fixture_scoped access only",
                "Do not enable external pilot login",
                "Obtain owner migration approval before durable uploads",
            ],
            "live_ingest_claimed": False,
            "collaboration_matching_claimed": False,
            "upload_persistence_claimed": False,
            "final_export_claimed": False,
        }
    )


def customer_pilot_auth_demo_surface_invariant_failures(
    surface: dict[str, Any],
) -> list[str]:
    fails: list[str] = []
    for key in (
        "login_live_claimed",
        "production_auth_claimed",
        "rbac_enforced_claimed",
        "production_multi_tenant_claimed",
        "customer_data_isolation_claimed",
        "live_ingest_claimed",
        "collaboration_matching_claimed",
        "upload_persistence_claimed",
        "final_export_claimed",
    ):
        if surface.get(key) is True:
            fails.append(key)
    if surface.get("controlled_customer_pilot_status") == "GO":
        fails.append("customer_pilot_go")
    if surface.get("isolation_check_fails"):
        fails.extend([f"iso:{x}" for x in surface["isolation_check_fails"]])
    for b in surface.get("boundaries") or []:
        fails.extend(customer_access_boundary_invariant_failures(b))
    return fails
