"""Per-org package state + cohort rollup assembler (Campaign Block 19)."""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services.controlled_drafting_assembler_service import (
    build_controlled_drafting_demo_surface,
)
from nativeforge.services.forms_attachments_mapper_service import (
    build_forms_attachments_demo_surface,
)
from nativeforge.services.multi_org_pilot_cohort_contract_service import (
    build_multi_org_pilot_cohort_contract,
    multi_org_pilot_cohort_invariant_failures,
)
from nativeforge.services.organization_evidence_memory_assembler_service import (
    build_organization_evidence_demo_surface,
)
from nativeforge.services.package_export_preview_assembler_service import (
    build_package_export_preview_demo_surface,
)
from nativeforge.services.package_readiness_queue_assembler_service import (
    build_package_readiness_demo_surface,
)
from nativeforge.services.proposal_qa_gate_service import (
    build_ai_governance_demo_surface,
)

SCHEMA_VERSION = "nf_multi_org_pilot_assembler_v1"

# First SC Native/tribal pilot cohort (fixture/demo-safe profile IDs)
DEFAULT_COHORT_ORG_IDS: tuple[str, ...] = (
    "sc_pilot_catawba_indian_nation",
    "sc_pilot_waccamaw_indian_people",
    "sc_pilot_edisto_natchez_kusso_tribe_of_south_carolina",
    "sc_pilot_pee_dee_indian_nation_of_upper_south_carolina",
)


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _index_by_org(items: list[dict[str, Any]], key: str = "organization_profile_id"):
    out: dict[str, list[dict[str, Any]]] = {}
    for item in items:
        oid = str(item.get(key) or "")
        if not oid:
            continue
        out.setdefault(oid, []).append(item)
    return out


def build_per_org_package_state(
    *,
    organization_profile_id: str,
    org_card: dict[str, Any] | None,
    readiness_items: list[dict[str, Any]],
    gov_items: list[dict[str, Any]],
    export_items: list[dict[str, Any]],
    forms_items: list[dict[str, Any]],
    controlled_items: list[dict[str, Any]],
) -> dict[str, Any]:
    """Assemble isolated package state for one org — never mixes other org IDs."""
    blockers: list[str] = []
    customer_actions: list[str] = []
    operator_actions: list[str] = []
    for r in readiness_items:
        blockers.extend(list(r.get("blocked_reasons") or [])[:3])
        customer_actions.extend(list(r.get("customer_actions") or [])[:2])
        operator_actions.extend(list(r.get("operator_actions") or [])[:2])
    qa_blockers = 0
    for g in gov_items:
        qa_blockers += int(g.get("blocker_count") or 0)
        if g.get("hard_blockers"):
            blockers.extend(
                [
                    str(b.get("issue_summary") or b.get("check_scope"))
                    for b in (g.get("hard_blockers") or [])[:2]
                ]
            )
    # Isolation proof: reject foreign org IDs if present
    for bucket in (
        readiness_items,
        gov_items,
        export_items,
        forms_items,
        controlled_items,
    ):
        for item in bucket:
            if item.get("organization_profile_id") not in {
                None,
                organization_profile_id,
            }:
                blockers.append(
                    f"isolation_violation:{item.get('organization_profile_id')}"
                )

    readiness_statuses = [
        str(r.get("overall_readiness_status") or "not_submission_ready")
        for r in readiness_items
    ]
    package_ids = [
        str(r.get("application_workspace_id") or r.get("package_readiness_id") or "")
        for r in readiness_items
        if r.get("application_workspace_id") or r.get("package_readiness_id")
    ]
    feedback_context_id = f"fbctx_{organization_profile_id}"

    return _json_safe(
        {
            "organization_profile_id": organization_profile_id,
            "organization_name": (org_card or {}).get("organization_name"),
            "recognition_status": (org_card or {}).get("recognition_status")
            or (org_card or {}).get("recognition_tier"),
            "organization_evidence_profile_id": (org_card or {}).get(
                "organization_evidence_profile_id"
            ),
            "evidence_memory": {
                "present": bool(org_card),
                "missing_evidence": list(
                    (org_card or {}).get("missing_evidence") or []
                )[:5],
                "standard_attachment_count": len(
                    (org_card or {}).get("standard_attachments") or []
                ),
            },
            "package_workspace_ids": [p for p in package_ids if p],
            "readiness_statuses": readiness_statuses,
            "overall_readiness_status": (
                readiness_statuses[0] if readiness_statuses else "not_started"
            ),
            "opportunity_count": len(readiness_items),
            "blockers": list(dict.fromkeys(blockers))[:12],
            "qa_blocker_count": qa_blockers,
            "customer_actions": list(dict.fromkeys(customer_actions))[:6],
            "operator_actions": list(dict.fromkeys(operator_actions))[:6],
            "controlled_draft_count": len(controlled_items),
            "export_preview_count": len(export_items),
            "forms_map_count": len(forms_items),
            "feedback_context_id": feedback_context_id,
            "export_allowed": False,
            "submission_ready_claimed": False,
            "final_export_claimed": False,
            "final_eligibility_claimed": False,
            "live_ingest_claimed": False,
            "human_review_required": True,
            "next_safest_action": (
                "Resolve org-specific blockers and complete human review before export"
            ),
            "data_mode": "fixture_backed_pilot",
        }
    )


def build_cohort_operator_rollup(
    *,
    cohort: dict[str, Any],
    org_states: list[dict[str, Any]],
) -> dict[str, Any]:
    blockers_by_org = {
        s["organization_profile_id"]: list(s.get("blockers") or []) for s in org_states
    }
    readiness_by_org = {
        s["organization_profile_id"]: s.get("overall_readiness_status")
        for s in org_states
    }
    return _json_safe(
        {
            "pilot_cohort_id": cohort.get("pilot_cohort_id"),
            "org_count": len(org_states),
            "package_count": sum(
                len(s.get("package_workspace_ids") or []) for s in org_states
            ),
            "opportunities_under_review": sum(
                int(s.get("opportunity_count") or 0) for s in org_states
            ),
            "blockers_by_org": blockers_by_org,
            "readiness_by_org": readiness_by_org,
            "customer_actions_by_org": {
                s["organization_profile_id"]: s.get("customer_actions") or []
                for s in org_states
            },
            "operator_actions_by_org": {
                s["organization_profile_id"]: s.get("operator_actions") or []
                for s in org_states
            },
            "qa_blockers_by_org": {
                s["organization_profile_id"]: s.get("qa_blocker_count") or 0
                for s in org_states
            },
            "feedback_context_by_org": {
                s["organization_profile_id"]: s.get("feedback_context_id")
                for s in org_states
            },
            "unsupported_capability_counts": {
                "live_customer_login": 0,
                "production_multi_tenant": 0,
                "collaboration_matching": 0,
                "durable_upload_persistence": 0,
            },
            "source_data_mode_label": cohort.get("cohort_data_mode"),
            "next_safest_action_per_org": {
                s["organization_profile_id"]: s.get("next_safest_action")
                for s in org_states
            },
            "cohort_next_safest_action": (
                "Keep orgs isolated; clear per-org blockers; leave collaboration OFF"
            ),
            "collaboration_enabled": False,
            "production_multi_tenant_claimed": False,
            "live_customer_login_claimed": False,
        }
    )


def build_multi_org_pilot_demo_surface(
    *,
    org_ids: tuple[str, ...] | list[str] | None = None,
) -> dict[str, Any]:
    selected = list(org_ids or DEFAULT_COHORT_ORG_IDS)
    org_surface = build_organization_evidence_demo_surface(max_profiles=8)
    readiness = build_package_readiness_demo_surface()
    gov = build_ai_governance_demo_surface()
    export = build_package_export_preview_demo_surface()
    forms = build_forms_attachments_demo_surface()
    controlled = build_controlled_drafting_demo_surface()

    org_by_id = {
        c.get("organization_profile_id"): c for c in (org_surface.get("cards") or [])
    }
    readiness_by = _index_by_org(list(readiness.get("workspaces") or []))
    gov_by = _index_by_org(list(gov.get("workspaces") or []))
    export_by = _index_by_org(list(export.get("workspaces") or []))
    forms_by = _index_by_org(list(forms.get("workspaces") or []))
    controlled_by = _index_by_org(list(controlled.get("workspaces") or []))

    org_states: list[dict[str, Any]] = []
    for oid in selected:
        # Ensure card exists even if only name stub for isolation demo
        card = org_by_id.get(oid) or {
            "organization_profile_id": oid,
            "organization_name": oid.replace("sc_pilot_", "").replace("_", " ").title(),
            "recognition_status": "unknown",
            "missing_evidence": ["profile_stub_fixture"],
            "standard_attachments": [],
        }
        state = build_per_org_package_state(
            organization_profile_id=oid,
            org_card=card,
            readiness_items=readiness_by.get(oid, []),
            gov_items=gov_by.get(oid, []),
            export_items=export_by.get(oid, []),
            forms_items=forms_by.get(oid, []),
            controlled_items=controlled_by.get(oid, []),
        )
        org_states.append(state)

    package_ids = [
        pid for s in org_states for pid in (s.get("package_workspace_ids") or [])
    ]
    readiness_ids = [f"rr_{s['organization_profile_id']}" for s in org_states]
    feedback_ids = [s["feedback_context_id"] for s in org_states]

    cohort = build_multi_org_pilot_cohort_contract(
        cohort_label="SC Native/tribal pilot cohort v0",
        cohort_data_mode="fixture_backed_pilot",
        organization_profile_ids=selected,
        package_workspace_ids=package_ids,
        readiness_rollup_ids=readiness_ids,
        feedback_context_ids=feedback_ids,
    )
    rollup = build_cohort_operator_rollup(cohort=cohort, org_states=org_states)

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "campaign_block": 19,
            "title": "Multi-organization pilot / cohort readiness",
            "cohort": cohort,
            "organizations": org_states,
            "selected_organization_profile_id": selected[0] if selected else None,
            "operator_rollup": rollup,
            "buyer_summary": [
                "Multiple SC Native/tribal org profiles with isolated package state",
                "Per-org evidence, readiness, blockers, and feedback context",
                "Cohort operator rollup — collaboration remains OFF",
                "Fixture/demo-safe; production multi-tenant and live login not claimed",
            ],
            "collaboration_enabled": False,
            "customer_data_persistence_claimed": False,
            "production_multi_tenant_claimed": False,
            "live_customer_login_claimed": False,
            "live_ingest_claimed": False,
            "submission_ready_claimed": False,
            "final_export_claimed": False,
            "human_review_required": True,
        }
    )


def multi_org_pilot_demo_surface_invariant_failures(
    surface: dict[str, Any],
) -> list[str]:
    fails: list[str] = []
    for key in (
        "collaboration_enabled",
        "customer_data_persistence_claimed",
        "production_multi_tenant_claimed",
        "live_customer_login_claimed",
        "live_ingest_claimed",
        "submission_ready_claimed",
        "final_export_claimed",
    ):
        if surface.get(key) is True:
            fails.append(key)
    cohort = surface.get("cohort") or {}
    fails.extend(multi_org_pilot_cohort_invariant_failures(cohort))
    orgs = surface.get("organizations") or []
    if len(orgs) < 2:
        fails.append("need_multi_org")
    # Cross-org leakage: no org state may contain another org's profile id in evidence
    ids = {o.get("organization_profile_id") for o in orgs}
    for o in orgs:
        oid = o.get("organization_profile_id")
        for b in o.get("blockers") or []:
            if str(b).startswith("isolation_violation:"):
                fails.append(f"leak:{oid}")
        for other in ids:
            if other and other != oid:
                blob = json.dumps(o.get("evidence_memory") or {})
                if other in blob:
                    fails.append(f"evidence_leak:{oid}->{other}")
    return fails
