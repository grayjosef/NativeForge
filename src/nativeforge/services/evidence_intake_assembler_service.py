"""Evidence intake assembler + unlock rules + fixture adapter (Block 21)."""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services.evidence_intake_contract_service import (
    build_evidence_intake_record,
    evidence_intake_invariant_failures,
    evidence_may_contribute_to_unlock,
)
from nativeforge.services.forms_attachments_mapper_service import (
    build_forms_attachments_demo_surface,
)
from nativeforge.services.multi_org_pilot_assembler_service import (
    DEFAULT_COHORT_ORG_IDS,
)
from nativeforge.services.package_export_preview_assembler_service import (
    build_package_export_preview_demo_surface,
)
from nativeforge.services.package_readiness_queue_assembler_service import (
    build_package_readiness_demo_surface,
)

SCHEMA_VERSION = "nf_evidence_intake_assembler_v1"


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def build_fixture_evidence_intake_records(
    *,
    organization_profile_id: str,
    forms_ws: dict[str, Any] | None,
    readiness_ws: dict[str, Any] | None,
    export_ws: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    """Demo-safe planned/fixture records — not durable file bytes."""
    records: list[dict[str, Any]] = []
    missing = list((forms_ws or {}).get("missing_attachments") or [])
    if not missing:
        # Conservative placeholders when forms map lacks attachment rows for org
        missing = [
            {
                "item_id": "uei_sam",
                "label": "SAM / UEI evidence",
                "requirement_status": "needs_confirmation",
            },
            {
                "item_id": "letters_of_support",
                "label": "Letters of support",
                "requirement_status": "needs_confirmation",
            },
        ]
    map_id = (forms_ws or {}).get("forms_attachment_map_id")
    app_id = (readiness_ws or {}).get("application_workspace_id") or (
        forms_ws or {}
    ).get("application_workspace_id")
    pursuit_id = (readiness_ws or {}).get("pursuit_workspace_id") or (
        forms_ws or {}
    ).get("pursuit_workspace_id")
    export_id = (export_ws or {}).get("package_export_preview_id")

    for att in missing[:6]:
        label = str(att.get("label") or att.get("item_id") or "attachment")
        item_id = str(att.get("item_id") or label)
        records.append(
            build_evidence_intake_record(
                organization_profile_id=organization_profile_id,
                evidence_label=label,
                evidence_type="attachment_needed",
                application_workspace_id=str(app_id) if app_id else None,
                pursuit_workspace_id=str(pursuit_id) if pursuit_id else None,
                checklist_item_id=f"checklist:{item_id}",
                binder_item_id=f"binder:{item_id}",
                forms_attachment_map_id=str(map_id) if map_id else None,
                package_export_preview_id=str(export_id) if export_id else None,
                source_context="forms_attachments_map+org_evidence_memory",
                storage_mode="fixture_backed",
                storage_reference=f"fixtures/evidence_intake_pilot/{item_id}.placeholder",
                review_status="needs_review",
                human_review_required=True,
                file_name=None,
                mime_type=None,
                size_bytes=None,
            )
        )
    # Always include one planned external-storage-required sentinel
    records.append(
        build_evidence_intake_record(
            organization_profile_id=organization_profile_id,
            evidence_label="Durable binary upload (planned)",
            evidence_type="binary_upload_planned",
            application_workspace_id=str(app_id) if app_id else None,
            pursuit_workspace_id=str(pursuit_id) if pursuit_id else None,
            forms_attachment_map_id=str(map_id) if map_id else None,
            package_export_preview_id=str(export_id) if export_id else None,
            source_context="storage_proposal",
            storage_mode="external_storage_required",
            storage_reference=None,
            review_status="not_supported",
            human_review_required=True,
        )
    )
    return records


def evaluate_package_unlock_from_evidence(
    records: list[dict[str, Any]],
) -> dict[str, Any]:
    contributing = [r for r in records if evidence_may_contribute_to_unlock(r)]
    # Gate 08: never unlock — fixture/planned modes cannot unlock
    unlock = False
    blockers = []
    for r in records:
        if r.get("review_status") != "approved":
            blockers.append(
                f"review:{r.get('evidence_intake_id')}:{r.get('review_status')}"
            )
        if r.get("storage_mode") != "validated_persistent":
            blockers.append(
                f"storage:{r.get('evidence_intake_id')}:{r.get('storage_mode')}"
            )
        if (
            r.get("human_review_required") is True
            and r.get("review_status") != "approved"
        ):
            blockers.append(f"human_review:{r.get('evidence_intake_id')}")
    return {
        "package_unlock_claimed": unlock,
        "submission_ready_claimed": False,
        "final_export_claimed": False,
        "contributing_evidence_count": len(contributing),
        "blockers": list(dict.fromkeys(blockers))[:20],
        "reason": (
            "Evidence intake is fixture/planned only; human review + validated "
            "persistent storage required before any package unlock"
        ),
    }


def build_evidence_intake_demo_surface(*, max_orgs: int = 2) -> dict[str, Any]:
    forms = build_forms_attachments_demo_surface(max_workspaces=4)
    readiness = build_package_readiness_demo_surface()
    export = build_package_export_preview_demo_surface(max_workspaces=4)

    forms_by_org: dict[str, list[dict[str, Any]]] = {}
    for ws in forms.get("workspaces") or []:
        oid = str(ws.get("organization_profile_id") or "")
        forms_by_org.setdefault(oid, []).append(ws)
    readiness_by_org: dict[str, list[dict[str, Any]]] = {}
    for ws in readiness.get("workspaces") or []:
        oid = str(ws.get("organization_profile_id") or "")
        readiness_by_org.setdefault(oid, []).append(ws)
    export_by_org: dict[str, list[dict[str, Any]]] = {}
    for ws in export.get("workspaces") or []:
        oid = str(ws.get("organization_profile_id") or "")
        export_by_org.setdefault(oid, []).append(ws)

    org_ids = list(DEFAULT_COHORT_ORG_IDS)[:max_orgs]
    # Prefer orgs that appear in readiness/forms
    if readiness_by_org:
        preferred = [o for o in org_ids if o in readiness_by_org] or list(
            readiness_by_org.keys()
        )[:max_orgs]
        org_ids = preferred[:max_orgs]

    workspaces: list[dict[str, Any]] = []
    for oid in org_ids:
        fws = (forms_by_org.get(oid) or [None])[0]
        rws = (readiness_by_org.get(oid) or [None])[0]
        ews = (export_by_org.get(oid) or [None])[0]
        records = build_fixture_evidence_intake_records(
            organization_profile_id=oid,
            forms_ws=fws,
            readiness_ws=rws,
            export_ws=ews,
        )
        unlock = evaluate_package_unlock_from_evidence(records)
        workspaces.append(
            {
                "organization_profile_id": oid,
                "record_count": len(records),
                "records": records,
                "unlock_evaluation": unlock,
                "customer_actions": [
                    "Provide requested evidence when durable upload path is approved",
                    "Do not assume fixture placeholders are stored customer files",
                ],
                "operator_actions": [
                    "Review evidence labels and linkage",
                    "Do not unlock package/export until validated persistence + review",
                ],
                "upload_persistence_claimed": False,
                "customer_data_persistence_claimed": False,
                "production_storage_claimed": False,
                "package_unlock_claimed": False,
                "submission_ready_claimed": False,
                "final_export_claimed": False,
                "human_review_required": True,
                "storage_adapter": "fixture_planned_only",
                "upload_ui_supported": False,
            }
        )

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "campaign_block": 21,
            "title": "Evidence intake / uploads",
            "workspace_count": len(workspaces),
            "workspaces": workspaces,
            "buyer_summary": [
                "Evidence intake contract links gaps to checklist/binder/forms/preview",
                "Storage mode is fixture/planned — durable binary upload not claimed",
                "Human review required; package unlock remains false",
                "Storage proposal documents migration/infra before production persistence",
            ],
            "storage_modes_in_use": ["fixture_backed", "external_storage_required"],
            "storage_adapter": "fixture_planned_only",
            "upload_ui_supported": False,
            "upload_persistence_claimed": False,
            "customer_data_persistence_claimed": False,
            "production_storage_claimed": False,
            "package_unlock_claimed": False,
            "submission_ready_claimed": False,
            "final_export_claimed": False,
            "migration_required": True,
            "storage_proposal_path": (
                "docs/operations/161_EVIDENCE_UPLOAD_STORAGE_PROPOSAL.md"
            ),
            "human_review_required": True,
            "live_ingest_claimed": False,
        }
    )


def evidence_intake_demo_surface_invariant_failures(
    surface: dict[str, Any],
) -> list[str]:
    fails: list[str] = []
    for key in (
        "upload_persistence_claimed",
        "customer_data_persistence_claimed",
        "production_storage_claimed",
        "package_unlock_claimed",
        "submission_ready_claimed",
        "final_export_claimed",
        "upload_ui_supported",
        "live_ingest_claimed",
    ):
        if surface.get(key) is True:
            fails.append(key)
    if (surface.get("workspace_count") or 0) < 1:
        fails.append("no_workspaces")
    for ws in surface.get("workspaces") or []:
        for key in (
            "upload_persistence_claimed",
            "package_unlock_claimed",
            "submission_ready_claimed",
            "final_export_claimed",
        ):
            if ws.get(key) is True:
                fails.append(f"ws:{key}")
        for rec in ws.get("records") or []:
            fails.extend(evidence_intake_invariant_failures(rec))
        unlock = ws.get("unlock_evaluation") or {}
        if unlock.get("package_unlock_claimed") is True:
            fails.append("unlock_true")
    return fails
