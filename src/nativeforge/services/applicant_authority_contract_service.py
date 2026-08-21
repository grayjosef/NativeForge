"""Applicant authority verification contract (Campaign Block 28)."""

from __future__ import annotations

import hashlib
import json
from typing import Any

SCHEMA_VERSION = "nf_applicant_authority_contract_v1"

AUTHORITY_TYPES = frozenset(
    {
        "view_only",
        "draft_contributor",
        "workspace_manager",
        "grant_administrator",
        "authorized_signer",
        "AOR",
        "Expanded_AOR",
        "EBiz_POC",
        "tribal_chair_or_chief",
        "tribal_council_delegate",
        "fiscal_sponsor_delegate",
        "unknown",
    }
)

AUTHORITY_STATUSES = frozenset(
    {
        "not_started",
        "claimed_by_user",
        "needs_verification",
        "partially_verified",
        "verified_for_drafting",
        "verified_for_management",
        "verified_for_submission",
        "rejected",
        "expired",
        "not_supported",
    }
)

JURISDICTION_SCOPES = frozenset({"federal", "state", "tribal", "unknown"})


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def make_applicant_authority_id(
    person_id: str, organization_profile_id: str, grant_context: str
) -> str:
    raw = f"aa::{person_id}::{organization_profile_id}::{grant_context}".encode()
    return f"aa_{hashlib.sha256(raw).hexdigest()[:16]}"


def build_applicant_authority_record(
    *,
    person_id: str,
    person_name: str,
    organization_profile_id: str,
    organization_type: str,
    grant_context: str,
    jurisdiction_scope: str,
    opportunity_id: str | None = None,
    authority_type: str = "unknown",
    authority_status: str = "needs_verification",
    authority_evidence_refs: list[str] | None = None,
    required_evidence: list[str] | None = None,
    missing_evidence: list[str] | None = None,
    verification_source: str = "not_live_verified",
    verification_confidence: str = "low",
    human_review_required: bool = True,
    draft_authority_claimed: bool = False,
    manage_workspace_authority_claimed: bool = False,
) -> dict[str, Any]:
    at = authority_type if authority_type in AUTHORITY_TYPES else "unknown"
    status = (
        authority_status
        if authority_status in AUTHORITY_STATUSES
        else "needs_verification"
    )
    jur = jurisdiction_scope if jurisdiction_scope in JURISDICTION_SCOPES else "unknown"
    refs = list(authority_evidence_refs or [])
    required = list(required_evidence or [])
    missing = list(missing_evidence or [])
    if not missing and required and not refs:
        missing = list(required)

    # Hard: never claim submission/federal/state authority without evidence
    submission_authority_claimed = False
    federal_authority_claimed = False
    state_authority_claimed = False

    # Draft/manage only if status supports and not submission
    if status not in {
        "verified_for_drafting",
        "verified_for_management",
        "verified_for_submission",
    }:
        draft_authority_claimed = False
        manage_workspace_authority_claimed = False
    if status == "verified_for_drafting":
        manage_workspace_authority_claimed = False
    if status == "verified_for_submission":
        # Still do not auto-claim submission without complete evidence
        if missing or not refs:
            submission_authority_claimed = False
            status = "partially_verified"

    # Self-attestation alone is never enough
    if verification_source in {"self_attestation", "claimed_by_user_only"}:
        submission_authority_claimed = False
        federal_authority_claimed = False
        state_authority_claimed = False
        if status == "claimed_by_user":
            status = "needs_verification"

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "applicant_authority_id": make_applicant_authority_id(
                person_id, organization_profile_id, grant_context
            ),
            "person_id": person_id,
            "person_name": person_name,
            "organization_profile_id": organization_profile_id,
            "organization_type": organization_type,
            "grant_context": grant_context,
            "jurisdiction_scope": jur,
            "opportunity_id": opportunity_id,
            "authority_type": at,
            "authority_status": status,
            "authority_evidence_refs": refs,
            "required_evidence": required,
            "missing_evidence": missing,
            "verification_source": verification_source,
            "verification_confidence": verification_confidence,
            "human_review_required": bool(human_review_required),
            "submission_authority_claimed": submission_authority_claimed,
            "draft_authority_claimed": bool(draft_authority_claimed),
            "manage_workspace_authority_claimed": bool(
                manage_workspace_authority_claimed
            ),
            "federal_authority_claimed": federal_authority_claimed,
            "state_authority_claimed": state_authority_claimed,
            "submission_ready_claimed": False,
            "final_export_claimed": False,
            "aor_verified_claimed": False,
            "ebiz_poc_verified_claimed": False,
            "sam_verified_claimed": False,
        }
    )


def applicant_authority_invariant_failures(record: dict[str, Any]) -> list[str]:
    fails: list[str] = []
    if record.get("authority_type") not in AUTHORITY_TYPES:
        fails.append("bad_authority_type")
    if record.get("authority_status") not in AUTHORITY_STATUSES:
        fails.append("bad_authority_status")
    for key in (
        "submission_authority_claimed",
        "federal_authority_claimed",
        "state_authority_claimed",
        "submission_ready_claimed",
        "final_export_claimed",
        "aor_verified_claimed",
        "ebiz_poc_verified_claimed",
        "sam_verified_claimed",
    ):
        if record.get(key) is True:
            fails.append(key)
    if record.get("human_review_required") is not True:
        # Always require human review in Gate 11
        fails.append("human_review_not_required")
    missing = record.get("missing_evidence") or []
    if missing and record.get("submission_authority_claimed") is True:
        fails.append("submission_with_missing_evidence")
    return fails
