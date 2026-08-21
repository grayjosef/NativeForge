"""Package export preview contract (Campaign Block 15)."""

from __future__ import annotations

import hashlib
import json
from typing import Any

SCHEMA_VERSION = "nf_package_export_preview_contract_v1"

EXPORT_MODES = frozenset(
    {
        "preview_only",
        "structured_package_preview",
        "evidence_map_preview",
        "review_packet_preview",
        "not_supported",
    }
)

EXPORT_STATUSES = frozenset(
    {
        "not_started",
        "preview_available",
        "blocked_missing_evidence",
        "blocked_qa",
        "blocked_human_review",
        "not_submission_ready",
        "not_supported",
    }
)


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def make_package_export_preview_id(application_workspace_id: str) -> str:
    raw = f"px::{application_workspace_id}".encode()
    return f"px_{hashlib.sha256(raw).hexdigest()[:16]}"


def build_package_export_preview_contract(
    *,
    application_workspace_id: str,
    pursuit_workspace_id: str,
    opportunity_id: str,
    organization_profile_id: str,
    organization_evidence_profile_id: str | None = None,
    package_readiness_id: str | None = None,
    draft_workspace_id: str | None = None,
    ai_governance_check_id: str | None = None,
    export_mode: str = "structured_package_preview",
    export_status: str = "not_submission_ready",
    preview_generated_at: str | None = None,
    included_sections: list[dict[str, Any]] | None = None,
    excluded_sections: list[dict[str, Any]] | None = None,
    missing_items: list[str] | None = None,
    blocked_items: list[str] | None = None,
    review_required_items: list[str] | None = None,
    evidence_map: list[dict[str, Any]] | None = None,
    human_review_required: bool = True,
    qa_blockers_present: bool = True,
) -> dict[str, Any]:
    mode = export_mode if export_mode in EXPORT_MODES else "preview_only"
    status = (
        export_status if export_status in EXPORT_STATUSES else "not_submission_ready"
    )
    # Hard rule: export never allowed while QA blockers or human review incomplete
    export_allowed = False
    if qa_blockers_present or human_review_required:
        export_allowed = False
        if status == "preview_available":
            status = "blocked_qa" if qa_blockers_present else "blocked_human_review"
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "package_export_preview_id": make_package_export_preview_id(
                application_workspace_id
            ),
            "application_workspace_id": application_workspace_id,
            "pursuit_workspace_id": pursuit_workspace_id,
            "opportunity_id": opportunity_id,
            "organization_profile_id": organization_profile_id,
            "organization_evidence_profile_id": organization_evidence_profile_id,
            "package_readiness_id": package_readiness_id,
            "draft_workspace_id": draft_workspace_id,
            "ai_governance_check_id": ai_governance_check_id,
            "export_mode": mode,
            "export_status": status,
            "preview_generated_at": preview_generated_at,
            "included_sections": list(included_sections or []),
            "excluded_sections": list(excluded_sections or []),
            "missing_items": list(missing_items or []),
            "blocked_items": list(blocked_items or []),
            "review_required_items": list(review_required_items or []),
            "evidence_map": list(evidence_map or []),
            "evidence_map_reference": "evidence_map_v0",
            "qa_gate_reference": ai_governance_check_id,
            "human_review_required": human_review_required,
            "export_allowed": export_allowed,
            "final_export_claimed": False,
            "submission_ready_claimed": False,
            "final_application_claimed": False,
            "final_eligibility_claimed": False,
            "live_ingest_claimed": False,
            "download_supported": False,
        }
    )


def package_export_preview_invariant_failures(preview: dict[str, Any]) -> list[str]:
    fails: list[str] = []
    for key in (
        "final_export_claimed",
        "submission_ready_claimed",
        "final_application_claimed",
        "final_eligibility_claimed",
        "live_ingest_claimed",
        "download_supported",
    ):
        if preview.get(key) is True:
            fails.append(key)
    if preview.get("export_allowed") is True and (
        preview.get("human_review_required") is True
        or preview.get("blocked_items")
        or preview.get("export_status")
        in {"blocked_qa", "blocked_human_review", "blocked_missing_evidence"}
    ):
        fails.append("export_allowed_with_blockers")
    if preview.get("export_mode") not in EXPORT_MODES:
        fails.append("bad_mode")
    if preview.get("export_status") not in EXPORT_STATUSES:
        fails.append("bad_status")
    return fails
