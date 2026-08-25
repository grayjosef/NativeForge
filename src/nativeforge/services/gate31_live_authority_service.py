"""Live authority verification execution path (Block 67)."""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services.audit_event_collector_service import (
    AuditEventCollector,
    new_collector,
)

SCHEMA_VERSION = "nf_gate31_live_authority_v1"

AUTHORITY_STATUSES = (
    "not_started",
    "modeled_only",
    "manual_evidence_required",
    "manual_evidence_attached",
    "human_review_required",
    "human_review_passed",
    "live_check_available",
    "live_check_attempted",
    "live_check_passed",
    "live_check_failed",
    "blocked_missing_evidence",
    "blocked_missing_authority",
    "blocked_not_supported",
    "unknown",
)

def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def resolve_live_authority(
    *,
    self_attestation: bool = False,
    state_recognized: bool = False,
    federally_recognized: bool = False,
    aor_evidence: bool = False,
    ebiz_evidence: bool = False,
    sam_uei_evidence: bool = False,
    tribal_delegation: bool = False,
    tribal_delegation_required: bool = True,
    state_portal_evidence: bool = False,
    manual_evidence_attached: bool = False,
    human_review_passed: bool = False,
    live_check_attempted: bool = False,
    live_check_passed: bool = False,
    collector: AuditEventCollector | None = None,
) -> dict[str, Any]:
    collector = new_collector(collector)
    missing: list[str] = []
    sam_status = "modeled_only"
    aor_status = "modeled_only"
    tribal_status = "manual_evidence_required"
    state_portal_status = "modeled_only"

    if sam_uei_evidence:
        sam_status = "manual_evidence_attached"
    if aor_evidence and ebiz_evidence:
        aor_status = "manual_evidence_attached"
    if tribal_delegation:
        tribal_status = "manual_evidence_attached"
    if state_portal_evidence:
        state_portal_status = "manual_evidence_attached"

    if live_check_attempted and live_check_passed and sam_uei_evidence:
        sam_status = "live_check_passed"
    elif live_check_attempted and not live_check_passed:
        sam_status = "live_check_failed"

    if not aor_evidence or not ebiz_evidence or not sam_uei_evidence:
        missing.append("federal_aor_ebiz_sam_uei")
    if tribal_delegation_required and not tribal_delegation:
        missing.append("tribal_delegation_resolution")
    if manual_evidence_attached and not human_review_passed:
        missing.append("human_review")
    if live_check_attempted and not live_check_passed:
        missing.append("live_check_failed")

    # View/draft allowed internally; submit never from self-attestation
    can_view = True
    can_draft = True
    can_manage = True
    can_upload = bool(manual_evidence_attached or tribal_delegation)
    can_approve = bool(human_review_passed and can_upload)
    can_submit = False
    federal_submit_ok = bool(
        federally_recognized
        and aor_evidence
        and ebiz_evidence
        and sam_uei_evidence
        and (not tribal_delegation_required or tribal_delegation)
        and human_review_passed
        and live_check_passed
        and not self_attestation  # attestation never sufficient
    )
    # Self-attestation cannot unlock submit even if other flags true
    if self_attestation and not (
        aor_evidence and ebiz_evidence and sam_uei_evidence and human_review_passed
    ):
        federal_submit_ok = False
    if self_attestation:
        can_submit = False
    # State recognition never unlocks federal authority
    if state_recognized and not federally_recognized:
        missing.append("federal_recognition_required_for_federal_submit")
        federal_submit_ok = False
    if live_check_attempted and not live_check_passed:
        federal_submit_ok = False
    if tribal_delegation_required and not tribal_delegation:
        federal_submit_ok = False
    if not (aor_evidence and ebiz_evidence and sam_uei_evidence):
        federal_submit_ok = False
    if manual_evidence_attached and not human_review_passed:
        federal_submit_ok = False
        human_review_required = True
    else:
        human_review_required = bool(
            manual_evidence_attached and not human_review_passed
        )
        if not human_review_passed:
            human_review_required = True

    can_submit = bool(federal_submit_ok)
    final_authority = can_submit
    collector.add({"event": "authority_resolve", "can_submit": can_submit})

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "authority_execution_contract": True,
            "statuses": list(AUTHORITY_STATUSES),
            "live_check_attempted": live_check_attempted,
            "sam_uei_status": sam_status,
            "grants_gov_aor_ebiz_status": aor_status,
            "tribal_delegation_resolution_status": tribal_status,
            "state_portal_authority_status": state_portal_status,
            "manual_evidence_fallback": True,
            "human_review_required": human_review_required or not can_submit,
            "can_view": can_view,
            "can_draft": can_draft,
            "can_manage_workspace": can_manage,
            "can_upload_evidence": can_upload,
            "can_approve_package": can_approve,
            "can_submit": can_submit,
            "final_authority_claim": final_authority,
            "final_eligibility_claim": False,
            "submission_ready_claim": False,
            "missing_evidence": missing,
            "missing_gates": missing,
            "audit_refs": collector.event_names(3),
            "state_recognized_is_not_federal": True,
            "self_attestation_cannot_submit": True,
        }
    )


def live_authority_invariant_failures(result: dict[str, Any]) -> list[str]:
    fails: list[str] = []
    if result.get("final_eligibility_claim") is True:
        fails.append("final_eligibility")
    if result.get("submission_ready_claim") is True:
        fails.append("submission_ready")
    if result.get("can_submit") and not result.get("final_authority_claim"):
        fails.append("submit_without_final_authority")
    return fails
