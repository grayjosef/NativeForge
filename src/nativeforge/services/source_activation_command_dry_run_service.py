"""Sprint 42: deterministic Activation Command Dry-Run package (no execution)."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from nativeforge.services import source_human_approval_artifact_service as haa_svc

SCHEMA_VERSION = "nf_source_activation_command_dry_run_v1"

_REVIEW_INTERVAL_DAYS: dict[str, int] = {
    "critical": 7,
    "weak": 14,
    "adequate": 30,
    "strong": 90,
}

_CMD_STATUS_RANK: dict[str, int] = {
    "dry_run_blocked_legal_tos": 0,
    "dry_run_blocked_missing_evidence": 1,
    "dry_run_not_ready": 2,
    "dry_run_blocked_unsigned_approval": 3,
    "dry_run_ready_after_signature": 4,
}

_RANK_TO_CMD_STATUS: dict[int, str] = {v: k for k, v in _CMD_STATUS_RANK.items()}

_PRE_EXECUTION_CHECKS: tuple[str, ...] = (
    "signed_human_approval_present",
    "approval_signature_fields_complete",
    "legal_tos_acknowledgment_complete",
    "native_relevance_acknowledgment_complete",
    "provenance_plan_complete",
    "freshness_strategy_complete",
    "dedupe_strategy_complete",
    "rollback_plan_reviewed",
    "no_customer_sensitive_data_required",
    "no_scraping_or_api_execution_without_separate_approval",
    "operator_activation_execution_review_required",
    "source_owner_or_public_access_basis_confirmed",
)


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _dry_run_command_id(
    organization_id: str,
    approval_artifact_id: str,
    candidate_id: str,
    schema_version: str,
) -> str:
    payload = "|".join(
        (organization_id, approval_artifact_id, candidate_id, schema_version)
    ).encode()
    digest = hashlib.sha256(payload).hexdigest()
    return f"nf_src_act_cmd_dry_v1_{digest[:24]}"


def _blockers_blob(blockers: list[Any]) -> str:
    return " ".join(str(b) for b in blockers).lower()


def _implies_legal_access_context(
    *,
    lane: str,
    source_type: str,
    snapshot: dict[str, Any],
    approval_recommendation: str,
) -> bool:
    st = source_type.lower()
    if st in {"foundation", "corporate", "university"}:
        return True
    method = str(snapshot.get("proposed_collection_method") or "").lower()
    if any(x in method for x in ("api", "portal", "monitoring")):
        return True
    if lane == "federal_native_relevant_broad":
        return True
    if approval_recommendation == "legal_tos_review_required":
        return True
    return False


def _classify_command(
    *,
    approval_status: str,
    preview_status: str,
    lane: str,
    missing_evidence: list[str],
    blockers: list[Any],
    approval_recommendation: str,
) -> tuple[str, str, str]:
    """Return (command_status, command_recommendation, proposed_command_type)."""
    blob = _blockers_blob(blockers)
    legal_hit = approval_recommendation == "legal_tos_review_required" or any(
        tok in blob
        for tok in (
            "legal",
            "tos",
            "robot",
            "access",
            "terms",
            "scraping",
            "api",
        )
    )
    if preview_status == "preview_only_blocked" and legal_hit:
        return (
            "dry_run_blocked_legal_tos",
            "complete_legal_tos_review",
            "legal_review_future",
        )
    if (
        approval_status == "unsigned_conditionally_ready"
        and lane == "federal_native_specific"
        and preview_status == "preview_only_conditionally_ready"
    ):
        return (
            "dry_run_ready_after_signature",
            "collect_signature_then_rerun_dry_run",
            "create_active_source_record_future",
        )
    if missing_evidence:
        return (
            "dry_run_blocked_missing_evidence",
            "resolve_evidence_gaps",
            "defer_activation_future",
        )
    if preview_status == "preview_only_not_ready":
        rec = (
            "continue_research"
            if lane == "general_broad_with_native_eligibility"
            else "defer"
        )
        return ("dry_run_not_ready", rec, "research_followup_future")
    if preview_status == "preview_only_review_required":
        if legal_hit:
            return (
                "dry_run_blocked_legal_tos",
                "complete_legal_tos_review",
                "legal_review_future",
            )
        rec = (
            "continue_research"
            if lane == "general_broad_with_native_eligibility"
            else "collect_signature_then_rerun_dry_run"
        )
        return (
            "dry_run_blocked_unsigned_approval",
            rec,
            "defer_activation_future",
        )
    if approval_status == "unsigned_conditionally_ready":
        return (
            "dry_run_blocked_missing_evidence",
            "resolve_evidence_gaps",
            "defer_activation_future",
        )
    if approval_status == "unsigned_blocked":
        if legal_hit:
            return (
                "dry_run_blocked_legal_tos",
                "complete_legal_tos_review",
                "legal_review_future",
            )
        return ("dry_run_not_ready", "defer", "defer_activation_future")
    if preview_status == "preview_only_blocked":
        return ("dry_run_not_ready", "defer", "defer_activation_future")
    return (
        "dry_run_blocked_unsigned_approval",
        "collect_signature_then_rerun_dry_run",
        "defer_activation_future",
    )


def _required_signed_fields() -> dict[str, bool]:
    return {
        "operator_name": True,
        "operator_role": True,
        "approval_timestamp": True,
        "approval_notes": True,
        "legal_tos_acknowledgment": True,
        "native_relevance_acknowledgment": True,
        "provenance_acknowledgment": True,
        "freshness_acknowledgment": True,
        "dedupe_acknowledgment": True,
    }


def _rollback_plan_row() -> dict[str, Any]:
    return {
        "disable_active_source_required": True,
        "preserve_provenance_snapshot_required": True,
        "audit_reason_required": True,
        "operator_rollback_approval_required": True,
        "downstream_ingestion_pause_required": True,
        "rollback_test_required_before_activation": True,
    }


def _dry_run_boundary_row() -> dict[str, Any]:
    return {
        "command_is_dry_run_only": True,
        "approval_is_unsigned": True,
        "approval_is_not_persisted": True,
        "may_execute_command_now": False,
        "may_persist_approval_now": False,
        "may_activate_source_now": False,
        "may_write_database_rows_now": False,
        "may_start_ingestion_now": False,
        "requires_signed_human_approval": True,
        "requires_future_activation_execution_sprint": True,
    }


def _missing_pre_execution_requirements(
    *,
    cmd_status: str,
    preview_status: str,
    lane: str,
    missing_evidence: list[str],
    legal_context: bool,
) -> list[str]:
    core = [
        "signed_human_approval_not_recorded",
        "approval_signature_fields_incomplete_pending_operator_signing",
        "operator_activation_execution_review_pending",
    ]
    if legal_context or cmd_status == "dry_run_blocked_legal_tos":
        core.append("legal_tos_acknowledgment_incomplete_until_review")
    if preview_status == "preview_only_not_ready":
        core.append("readiness_gates_incomplete_keyword_or_lane_review")
    if lane == "general_broad_with_native_eligibility":
        core.append("broad_native_eligibility_human_review_pending_not_confirmed")
    if preview_status == "preview_only_not_ready" and lane == (
        "general_broad_with_native_eligibility"
    ):
        core.append("native_relevance_keyword_only_not_confirmed_eligible")
    for ev in sorted(missing_evidence):
        core.append(f"evidence_gap:{ev}")
    if cmd_status == "dry_run_ready_after_signature":
        core.append("signature_packet_required_before_future_execution_sprint")
    return sorted(set(core))


def _unresolved_command_blockers(
    *,
    cmd_status: str,
    lane: str,
    preview_status: str,
    blockers: list[Any],
) -> list[str]:
    out = [str(b) for b in blockers]
    if lane == "general_broad_with_native_eligibility":
        out.append(
            "broad_native_catalog_eligibility_requires_explicit_human_confirmation"
        )
    if preview_status == "preview_only_not_ready" and lane == (
        "general_broad_with_native_eligibility"
    ):
        out.append("keyword_native_relevance_not_treated_as_eligibility_proof")
    if cmd_status == "dry_run_ready_after_signature":
        out.append(
            "federal_native_specific_planning_signal_only_unsigned_awaiting_signature"
        )
    return sorted(set(out))


def _cmd_risk_flags(*, commands: list[dict[str, Any]]) -> list[str]:
    flags = [
        "command_dry_run_only_no_execution",
        "unsigned_approval_required",
        "no_actual_activation_performed",
        "no_database_writes_performed",
        "future_activation_execution_sprint_required",
        "signed_human_approval_required",
        "approval_persistence_not_allowed",
        "rollback_plan_required",
        "provenance_evidence_missing",
        "freshness_strategy_missing",
        "dedupe_strategy_missing",
    ]
    if any(c.get("command_status") == "dry_run_blocked_legal_tos" for c in commands):
        flags.append("legal_tos_review_required")
    if any(c.get("lane") == "general_broad_with_native_eligibility" for c in commands):
        flags.append("broad_eligibility_review_required")
    if any(
        c.get("lane") == "general_broad_with_native_eligibility"
        and c.get("approval_status") == "unsigned_not_ready"
        for c in commands
    ):
        flags.append("keyword_only_review_required")
    if any(
        c.get("command_status") != "dry_run_ready_after_signature" for c in commands
    ):
        flags.append("blocked_commands_present")
    flags.append("no_executable_commands")
    return sorted(set(flags))


def _command_summary(
    *,
    org_id: str,
    posture: str,
    cmd_n: int,
    batch_n: int,
    ready_sig_n: int,
) -> str:
    tail = (
        "Sprint 42 activation command dry-run models future governed commands only: "
        "signed_approval_count, executable_command_count, actual_activation_count, "
        "and actual_database_write_count remain zero; no execution, persistence, "
        "activation, ingestion, scraping, external APIs, or operator ledger writes."
    )
    if posture == "strong":
        return (
            f"Organization {org_id}: command dry-run for {cmd_n} candidate-linked "
            f"rows across {batch_n} batches—strong posture favors conservative "
            f"maintenance sequencing language (not urgent activation). "
            f"{ready_sig_n} row(s) may surface dry_run_ready_after_signature after "
            f"future signatures only. {tail}"
        )
    if posture == "critical":
        return (
            f"Organization {org_id}: critical or sparse posture—{cmd_n} dry-run "
            f"commands with federal Native-specific batch emphasis for governance "
            f"alignment; {ready_sig_n} future-signature-ready row(s) at most. {tail}"
        )
    return (
        f"Organization {org_id}: activation command dry-run packet for {cmd_n} "
        f"commands in {batch_n} ordered batches—all unsigned and non-executable. "
        f"{tail}"
    )


def build_source_activation_command_dry_run(
    source_quality: dict[str, Any],
) -> dict[str, Any]:
    """Return nf_source_activation_command_dry_run_v1.

    Command dry-run only; performs no writes.
    """
    sq = dict(source_quality)
    ha = sq.get("source_human_approval_artifact")
    if not isinstance(ha, dict) or ha.get("schema_version") != haa_svc.SCHEMA_VERSION:
        ha = haa_svc.build_source_human_approval_artifact(sq)

    posture = str(
        (ha.get("approval_posture") or {}).get("source_quality_posture") or ""
    )
    dqs = int((ha.get("approval_posture") or {}).get("data_quality_score") or 0)
    active_n = int((ha.get("approval_posture") or {}).get("active_source_count") or 0)
    org_id = str((ha.get("organization_scope") or {}).get("organization_id") or "")
    gen_at = str((ha.get("organization_scope") or {}).get("generated_at") or "")

    artifacts: list[dict[str, Any]] = list(ha.get("approval_artifacts") or [])
    approval_n = len(artifacts)

    dry_run_commands: list[dict[str, Any]] = []
    by_cid_cmd_id: dict[str, str] = {}

    for art in artifacts:
        cid = str(art.get("candidate_id") or "")
        aid = str(art.get("approval_artifact_id") or "")
        lane = str(art.get("lane") or "")
        st = str(art.get("source_type") or "")
        name = str(art.get("source_name") or "")
        pri = str(art.get("priority") or "")
        appr_st = str(art.get("approval_status") or "")
        pv_st = str(art.get("preview_status") or "")
        miss_ev = sorted(
            set(str(x) for x in (art.get("missing_required_evidence") or []))
        )
        blockers = list(art.get("unresolved_blockers") or [])
        appr_rec = str(art.get("approval_recommendation") or "")
        snapshot = dict(art.get("proposed_active_source_record_snapshot") or {})

        cmd_id = _dry_run_command_id(org_id, aid, cid, SCHEMA_VERSION)
        by_cid_cmd_id[cid] = cmd_id

        legal_ctx = _implies_legal_access_context(
            lane=lane,
            source_type=st,
            snapshot=snapshot,
            approval_recommendation=appr_rec,
        )

        cmd_status, cmd_rec, proposed_type = _classify_command(
            approval_status=appr_st,
            preview_status=pv_st,
            lane=lane,
            missing_evidence=miss_ev,
            blockers=blockers,
            approval_recommendation=appr_rec,
        )

        row: dict[str, Any] = {
            "dry_run_command_id": cmd_id,
            "approval_artifact_id": aid,
            "candidate_id": cid,
            "source_name": name,
            "lane": lane,
            "source_type": st,
            "priority": pri,
            "approval_status": appr_st,
            "command_status": cmd_status,
            "command_recommendation": cmd_rec,
            "proposed_command_type": proposed_type,
            "proposed_active_source_record_snapshot": snapshot,
            "required_signed_approval_fields": _required_signed_fields(),
            "required_pre_execution_checks": sorted(_PRE_EXECUTION_CHECKS),
            "missing_pre_execution_requirements": _missing_pre_execution_requirements(
                cmd_status=cmd_status,
                preview_status=pv_st,
                lane=lane,
                missing_evidence=miss_ev,
                legal_context=legal_ctx,
            ),
            "unresolved_blockers": _unresolved_command_blockers(
                cmd_status=cmd_status,
                lane=lane,
                preview_status=pv_st,
                blockers=blockers,
            ),
            "rollback_plan": _rollback_plan_row(),
            "dry_run_boundary": _dry_run_boundary_row(),
            "dry_run_only": True,
            "can_become_active_source": False,
            "should_create_action": False,
        }
        dry_run_commands.append(_json_safe(row))

    ready_sig_n = sum(
        1
        for c in dry_run_commands
        if c["command_status"] == "dry_run_ready_after_signature"
    )
    blocked_n = sum(
        1
        for c in dry_run_commands
        if c["command_status"] != "dry_run_ready_after_signature"
    )

    command_batches: list[dict[str, Any]] = []
    for b in (ha.get("approval_batches") or {}).get("ordered_batches") or []:
        cids = list(b.get("candidate_ids") or [])
        st_list = [
            str(
                next(
                    (
                        x.get("command_status")
                        for x in dry_run_commands
                        if x.get("candidate_id") == cid
                    ),
                    "dry_run_not_ready",
                )
            )
            for cid in cids
        ]
        worst = min(_CMD_STATUS_RANK.get(s, 2) for s in st_list) if st_list else 2
        batch_cmd_st = _RANK_TO_CMD_STATUS.get(worst, "dry_run_not_ready")
        cmd_ids = [by_cid_cmd_id[c] for c in cids if c in by_cid_cmd_id]
        art_ids = list(b.get("approval_artifact_ids") or [])

        command_batches.append(
            _json_safe(
                {
                    "batch_number": int(b.get("batch_number") or 0),
                    "priority": str(b.get("priority") or ""),
                    "title": str(b.get("title") or ""),
                    "rationale": str(b.get("rationale") or ""),
                    "dry_run_command_ids": cmd_ids,
                    "approval_artifact_ids": art_ids,
                    "candidate_ids": cids,
                    "focus_lanes": list(b.get("focus_lanes") or []),
                    "batch_command_status": batch_cmd_st,
                    "required_batch_pre_execution_checks": sorted(
                        _PRE_EXECUTION_CHECKS
                    ),
                    "rollback_requirements": sorted(_rollback_plan_row().keys()),
                    "dry_run_only": True,
                    "should_create_action": False,
                }
            )
        )

    gb_notes = (
        "Sprint 42 command dry-run only: this package lists future activation-class "
        "commands that would require signed human approval artifacts first. "
        "No command executes here; no approvals persist; no sources activate; no "
        "database rows are written; no scraping, ingestion, external API calls, or "
        "operator ledger actions occur from this layer."
    )

    out: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "organization_scope": {
            "organization_id": org_id,
            "generated_at": gen_at,
        },
        "command_posture": {
            "source_quality_posture": posture,
            "data_quality_score": dqs,
            "active_source_count": active_n,
            "approval_artifact_count": approval_n,
            "unsigned_approval_count": approval_n,
            "signed_approval_count": 0,
            "dry_run_command_count": len(dry_run_commands),
            "executable_command_count": 0,
            "blocked_command_count": blocked_n,
            "actual_activation_count": 0,
            "actual_database_write_count": 0,
        },
        "dry_run_commands": dry_run_commands,
        "command_batches": {"ordered_batches": command_batches},
        "global_command_boundary": {
            "command_dry_run_only": True,
            "signed_approval_count": 0,
            "executable_command_count": 0,
            "actual_activation_count": 0,
            "actual_database_write_count": 0,
            "may_execute_commands_now": False,
            "may_persist_approvals_now": False,
            "may_activate_sources_now": False,
            "may_write_database_rows_now": False,
            "may_scrape_now": False,
            "may_ingest_now": False,
            "may_call_external_apis_now": False,
            "may_create_ledger_actions_now": False,
            "requires_signed_human_approval": True,
            "requires_future_activation_execution_sprint": True,
            "requires_rollback_plan_before_activation": True,
            "notes": gb_notes,
        },
        "risk_flags": _cmd_risk_flags(commands=dry_run_commands),
        "summary": _command_summary(
            org_id=org_id,
            posture=posture,
            cmd_n=len(dry_run_commands),
            batch_n=len(command_batches),
            ready_sig_n=ready_sig_n,
        ),
        "recommended_review_interval_days": int(_REVIEW_INTERVAL_DAYS.get(posture, 30)),
    }
    return _json_safe(out)
