"""Sprint 41: deterministic Human Approval Artifact.

Unsigned packet; no persistence.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from nativeforge.services import source_activation_preview_service as sap_svc
from nativeforge.services import (
    source_activation_readiness_contract_service as sarc_svc,
)

SCHEMA_VERSION = "nf_source_human_approval_artifact_v1"

_REVIEW_INTERVAL_DAYS: dict[str, int] = {
    "critical": 7,
    "weak": 14,
    "adequate": 30,
    "strong": 90,
}

_APPROVAL_STATUS_RANK: dict[str, int] = {
    "unsigned_blocked": 0,
    "unsigned_not_ready": 1,
    "unsigned_review_required": 2,
    "unsigned_conditionally_ready": 3,
}

_RANK_TO_APPROVAL_BATCH_STATUS: dict[int, str] = {
    v: k for k, v in _APPROVAL_STATUS_RANK.items()
}

_PREVIEW_TO_APPROVAL_STATUS: dict[str, str] = {
    "preview_only_blocked": "unsigned_blocked",
    "preview_only_not_ready": "unsigned_not_ready",
    "preview_only_review_required": "unsigned_review_required",
    "preview_only_conditionally_ready": "unsigned_conditionally_ready",
}

_BASE_ATTESTATIONS: tuple[str, ...] = (
    "I confirm this source is appropriate for NativeForge source monitoring.",
    "I confirm the source owner, publisher, or public access basis has been reviewed.",
    "I confirm legal/TOS/access review is complete or required before activation.",
    "I confirm no scraping, API polling, or ingestion is approved by this artifact.",
    "I confirm the Native relevance basis requires human judgment and is not "
    "inferred from keywords alone.",
    "I confirm broad eligibility is not the same as confirmed tribal eligibility.",
    "I confirm provenance fields are sufficient for future audit.",
    "I confirm freshness cadence and stale handling must be defined before activation.",
    "I confirm dedupe strategy must be defined before activation.",
    "I confirm no customer-sensitive data is required for source activation.",
)


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _approval_artifact_id(
    organization_id: str,
    candidate_id: str,
    schema_version: str,
) -> str:
    payload = f"{organization_id}|{candidate_id}|{schema_version}".encode()
    digest = hashlib.sha256(payload).hexdigest()
    return f"nf_src_human_approval_v1_{digest[:24]}"


def _preview_to_batch_approval_status(preview_batch_status: str) -> str:
    return {
        "preview_only_blocked": "unsigned_blocked",
        "preview_only_not_ready": "unsigned_not_ready",
        "preview_only_review_required": "unsigned_review_required",
        "preview_only_conditionally_ready": "unsigned_conditionally_ready",
    }.get(preview_batch_status, "unsigned_not_ready")


def _batch_approval_status(statuses: list[str]) -> str:
    if not statuses:
        return "unsigned_not_ready"
    worst = min(_APPROVAL_STATUS_RANK.get(s, 1) for s in statuses)
    return _RANK_TO_APPROVAL_BATCH_STATUS.get(worst, "unsigned_not_ready")


def _implies_legal_access_ack(
    lane: str,
    source_type: str,
    proposed: dict[str, Any],
) -> bool:
    st = source_type.lower()
    method = str(proposed.get("proposed_collection_method") or "").lower()
    if st in {"foundation", "corporate", "university"}:
        return True
    if "api" in method or "portal" in method:
        return True
    if lane == "federal_native_relevant_broad":
        return True
    return False


def _approval_recommendation(
    *,
    preview_status: str,
    lane: str,
    source_type: str,
    activation_blockers: list[Any],
) -> str:
    st = source_type.lower()
    if preview_status == "preview_only_blocked":
        blob = " ".join(str(b) for b in activation_blockers).lower()
        if any(x in blob for x in ("legal", "tos", "robot", "access", "terms")):
            return "legal_tos_review_required"
        return "defer"
    if preview_status == "preview_only_not_ready":
        return "defer"
    if preview_status == "preview_only_review_required":
        if lane == "general_broad_with_native_eligibility":
            return "continue_research"
        if st in {"foundation", "corporate", "university"}:
            return "legal_tos_review_required"
        return "continue_research"
    if preview_status == "preview_only_conditionally_ready":
        if lane == "federal_native_specific":
            return "approve_for_future_activation_dry_run"
        return "continue_research"
    return "defer"


def _operator_approval_statement(
    *,
    org_id: str,
    posture: str,
    lane: str,
    source_type: str,
    preview_status: str,
    recommendation: str,
) -> str:
    why = (
        "This sprint delivers an unsigned approval packet only: no activation, no "
        "database writes, no ingestion, no scraping, no external APIs, and no operator "
        "ledger actions. "
    )
    future = (
        "A future governed activation command dry-run and activation sprint remain "
        "required before active opportunity source creation."
    )
    if posture == "strong":
        stance = (
            "Strong portfolio posture: favor conservative maintenance diligence "
            "language rather than urgent activation framing. "
        )
    elif posture == "critical":
        stance = (
            "Critical or sparse posture: federal Native-specific ordering may lead "
            "batch emphasis for governance alignment; still no activation in this "
            "sprint. "
        )
    else:
        stance = ""

    if preview_status == "preview_only_conditionally_ready":
        if lane == "federal_native_specific":
            mid = (
                "Federal Native-specific conditional readiness is a planning signal "
                "only; "
                f"recommendation {recommendation} references a future dry-run, "
                "not live activation now. "
            )
        else:
            mid = (
                "Conditional readiness remains unsigned until attestations and "
                "evidence gates close in a future sprint. "
            )
    elif (
        preview_status == "preview_only_not_ready"
        and lane == "general_broad_with_native_eligibility"
    ):
        mid = (
            "Preview remains not ready (for example keyword-only Native relevance "
            "paths); extend research before any future activation discussion. "
        )
    elif lane == "general_broad_with_native_eligibility":
        mid = (
            "Broad Native-eligible lane: breadth does not equal confirmed tribal "
            "eligibility; keep human confirmation explicit. "
        )
    elif preview_status == "preview_only_not_ready":
        mid = (
            "Preview remains not ready; extend research before any future activation "
            "discussion. "
        )
    else:
        mid = ""

    head = (
        f"Organization {org_id}: operator approval statement for lane {lane} "
        f"({source_type})—unsigned artifact row. "
    )
    return _json_safe(" ".join((head, why, stance, mid, future)).strip())


def _required_operator_attestations(
    *,
    lane: str,
    preview_status: str,
) -> list[str]:
    out = list(_BASE_ATTESTATIONS)
    if lane == "general_broad_with_native_eligibility":
        out.append(
            "I confirm broad Native-eligible catalog rows remain subject to human "
            "eligibility judgment."
        )
    if preview_status == "preview_only_not_ready":
        out.append(
            "I confirm keyword-only or weak Native relevance signals are not treated "
            "as eligibility proof."
        )
    return sorted(set(out))


def _required_batch_attestations(
    *,
    batch_approval_status: str,
    posture: str,
) -> list[str]:
    core = [
        "I confirm this batch is an approval artifact packet only; no activation "
        "occurs in this sprint.",
        "I confirm approvals here are unsigned and not persisted to any ledger.",
        "I confirm no scraping, ingestion, database writes, or external API execution "
        "is authorized by this batch review.",
    ]
    if posture == "strong":
        core.append(
            "I confirm batch ordering favors maintenance diligence over urgent "
            "expansion."
        )
    if batch_approval_status == "unsigned_blocked":
        core.append(
            "I confirm blocked candidates require remediation before any future "
            "dry-run."
        )
    return sorted(core)


def _artifact_risk_flags(
    *,
    contracts: list[dict[str, Any]],
    cond_n: int,
    blocked_n: int,
) -> list[str]:
    flags = [
        "approval_artifact_only_no_signed_approval",
        "no_actual_activation_performed",
        "human_approval_required",
        "unsigned_approval_required",
        "future_activation_command_dry_run_required",
        "future_activation_sprint_required",
        "provenance_evidence_missing",
        "freshness_strategy_missing",
        "dedupe_strategy_missing",
    ]
    if any(
        c.get("legal_tos_contract", {}).get("tos_review_required") for c in contracts
    ):
        flags.append("legal_tos_review_required")
    if any(
        c.get("native_relevance_contract", {}).get(
            "broad_eligibility_human_review_required"
        )
        for c in contracts
    ):
        flags.append("broad_eligibility_review_required")
    if any(
        (c.get("native_relevance_contract") or {}).get(
            "keyword_only_not_confirmed_eligible"
        )
        for c in contracts
    ):
        flags.append("keyword_only_review_required")
    if blocked_n > 0:
        flags.append("blocked_candidates_present")
    if cond_n == 0:
        flags.append("no_conditionally_ready_preview_candidates")
    return sorted(set(flags))


def _approval_summary(
    *,
    org_id: str,
    posture: str,
    artifact_n: int,
    batch_n: int,
    cond_n: int,
) -> str:
    tail = (
        "Sprint 41 human approval artifact is documentation-only: "
        "signed_approval_count and actual_activation_count stay zero; no ledger "
        "persistence; future permitted command class after signatures and dry-run: "
        "nf_source_activation_command_dry_run_v1."
    )
    if posture == "strong":
        return (
            f"Organization {org_id}: unsigned approval artifacts ({artifact_n} rows, "
            f"{batch_n} batches). Strong posture: conservative maintenance-oriented "
            f"language without urgent activation emphasis. {tail}"
        )
    if posture == "critical":
        return (
            f"Organization {org_id}: unsigned approval packet "
            f"({artifact_n} artifacts); "
            "critical posture may emphasize federal Native-specific candidates first "
            f"in batch choreography; {cond_n} conditionally_ready preview row(s) "
            f"translate to unsigned_conditionally_ready only. {tail}"
        )
    return (
        f"Organization {org_id}: human approval artifact covering {artifact_n} "
        f"candidates across {batch_n} ordered batches—all unsigned, dry-run only. "
        f"{tail}"
    )


def build_source_human_approval_artifact(
    source_quality: dict[str, Any],
) -> dict[str, Any]:
    """Return nf_source_human_approval_artifact_v1 (unsigned; no writes)."""
    sq = dict(source_quality)
    preview = sq.get("source_activation_preview")
    if (
        not isinstance(preview, dict)
        or preview.get("schema_version") != sap_svc.SCHEMA_VERSION
    ):
        preview = sap_svc.build_source_activation_preview(sq)

    arc = sq.get("source_activation_readiness_contract")
    if (
        not isinstance(arc, dict)
        or arc.get("schema_version") != sarc_svc.SCHEMA_VERSION
    ):
        arc = sarc_svc.build_source_activation_readiness_contract(sq)

    contracts = list(arc.get("activation_contracts") or [])
    contracts_by_id: dict[str, dict[str, Any]] = {
        str(c.get("candidate_id") or ""): dict(c)
        for c in contracts
        if c.get("candidate_id")
    }

    pp = preview.get("preview_posture") or {}
    posture = str(pp.get("source_quality_posture") or "adequate")
    dqs = int(pp.get("data_quality_score") or 0)
    active_n = int(pp.get("active_source_count") or 0)
    org_id = str((preview.get("organization_scope") or {}).get("organization_id") or "")
    gen_at = str((preview.get("organization_scope") or {}).get("generated_at") or "")

    previews: list[dict[str, Any]] = list(preview.get("activation_previews") or [])
    preview_n = len(previews)
    review_req_n = sum(
        1
        for p in previews
        if p.get("source_activation_preview_status") == "preview_only_review_required"
    )
    cond_n = sum(
        1
        for p in previews
        if p.get("source_activation_preview_status")
        == "preview_only_conditionally_ready"
    )
    blocked_n = sum(
        1
        for p in previews
        if p.get("source_activation_preview_status") == "preview_only_blocked"
    )
    not_ready_n = sum(
        1
        for p in previews
        if p.get("source_activation_preview_status") == "preview_only_not_ready"
    )

    approval_rows: list[dict[str, Any]] = []
    by_candidate_artifact_id: dict[str, str] = {}

    for pr in previews:
        cid = str(pr.get("candidate_id") or "")
        lane = str(pr.get("lane") or "")
        st = str(pr.get("source_type") or "")
        name = str(pr.get("source_name") or "")
        pri = str(pr.get("priority") or "")
        pv_status = str(pr.get("source_activation_preview_status") or "")
        appr_status = _PREVIEW_TO_APPROVAL_STATUS.get(pv_status, "unsigned_not_ready")
        blockers = list(pr.get("activation_blockers") or [])
        proposed = dict(pr.get("proposed_active_source_record") or {})
        contract = contracts_by_id.get(cid, {})
        req_ev = sorted(set(str(x) for x in (contract.get("required_evidence") or [])))
        miss_ev = sorted(
            set(str(x) for x in (pr.get("missing_required_evidence") or []))
        )
        req_appr = sorted(
            set(str(x) for x in (pr.get("remaining_required_approvals") or []))
        )
        rec = _approval_recommendation(
            preview_status=pv_status,
            lane=lane,
            source_type=st,
            activation_blockers=blockers,
        )
        artifact_id = _approval_artifact_id(org_id, cid, SCHEMA_VERSION)
        by_candidate_artifact_id[cid] = artifact_id
        legal_ack = _implies_legal_access_ack(lane, st, proposed)

        row: dict[str, Any] = {
            "approval_artifact_id": artifact_id,
            "candidate_id": cid,
            "source_name": name,
            "lane": lane,
            "source_type": st,
            "priority": pri,
            "preview_status": pv_status,
            "approval_status": appr_status,
            "approval_recommendation": rec,
            "operator_approval_statement": _operator_approval_statement(
                org_id=org_id,
                posture=posture,
                lane=lane,
                source_type=st,
                preview_status=pv_status,
                recommendation=rec,
            ),
            "required_operator_attestations": _required_operator_attestations(
                lane=lane, preview_status=pv_status
            ),
            "required_approvals": req_appr,
            "required_evidence": req_ev,
            "missing_required_evidence": miss_ev,
            "unresolved_blockers": [str(x) for x in blockers],
            "proposed_active_source_record_snapshot": proposed,
            "approval_signature_block": {
                "operator_name_required": True,
                "operator_role_required": True,
                "approval_timestamp_required": True,
                "approval_notes_required": True,
                "legal_tos_acknowledgment_required": bool(legal_ack),
                "native_relevance_acknowledgment_required": True,
                "provenance_acknowledgment_required": True,
                "freshness_acknowledgment_required": True,
                "dedupe_acknowledgment_required": True,
            },
            "approval_boundary": {
                "approval_record_is_unsigned": True,
                "approval_is_not_persisted": True,
                "may_approve_now": False,
                "may_activate_source_now": False,
                "may_write_database_rows_now": False,
                "requires_future_activation_command_dry_run": True,
                "requires_future_activation_sprint": True,
            },
            "dry_run_only": True,
            "can_become_active_source": False,
            "should_create_action": False,
        }
        approval_rows.append(_json_safe(row))

    batch_out: list[dict[str, Any]] = []
    preview_by_cid: dict[str, dict[str, Any]] = {
        str(p.get("candidate_id") or ""): p for p in previews if p.get("candidate_id")
    }
    for b in (preview.get("activation_preview_batches") or {}).get(
        "ordered_batches"
    ) or []:
        cids = list(b.get("candidate_ids") or [])
        st_list: list[str] = []
        for cid in cids:
            pr_row = preview_by_cid.get(cid)
            pv_st = (
                str(pr_row.get("source_activation_preview_status") or "")
                if pr_row
                else "preview_only_not_ready"
            )
            if not pv_st:
                pv_st = "preview_only_not_ready"
            st_list.append(_PREVIEW_TO_APPROVAL_STATUS.get(pv_st, "unsigned_not_ready"))
        batch_appr_st = _batch_approval_status(st_list)

        artifact_ids = [
            by_candidate_artifact_id[c] for c in cids if c in by_candidate_artifact_id
        ]
        batch_out.append(
            _json_safe(
                {
                    "batch_number": int(b.get("batch_number") or 0),
                    "priority": str(b.get("priority") or ""),
                    "title": str(b.get("title") or ""),
                    "rationale": str(b.get("rationale") or ""),
                    "approval_artifact_ids": artifact_ids,
                    "candidate_ids": cids,
                    "focus_lanes": list(b.get("focus_lanes") or []),
                    "batch_approval_status": batch_appr_st,
                    "required_batch_attestations": _required_batch_attestations(
                        batch_approval_status=batch_appr_st,
                        posture=posture,
                    ),
                    "dry_run_only": True,
                    "should_create_action": False,
                }
            )
        )

    risk_flags = _artifact_risk_flags(
        contracts=contracts,
        cond_n=cond_n,
        blocked_n=blocked_n,
    )

    review_days = int(_REVIEW_INTERVAL_DAYS.get(posture, 30))

    gb_notes = (
        "Sprint 41 human approval artifact is unsigned paperwork only: no approval "
        "persistence, no activation, no database writes, no scraping, no ingestion, no "
        "external API calls, and no operator ledger actions. Future pathway: operator "
        "signatures on a separate governed step, then nf_source_activation_command_"
        "dry_run_v1, then a future activation sprint."
    )

    out: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "organization_scope": {
            "organization_id": org_id,
            "generated_at": gen_at,
        },
        "approval_posture": {
            "source_quality_posture": posture,
            "data_quality_score": dqs,
            "active_source_count": active_n,
            "preview_candidate_count": preview_n,
            "review_required_count": review_req_n,
            "conditionally_ready_preview_count": cond_n,
            "blocked_preview_count": blocked_n,
            "not_ready_preview_count": not_ready_n,
            "approval_artifact_count": len(approval_rows),
            "signed_approval_count": 0,
            "actual_activation_count": 0,
        },
        "approval_artifacts": approval_rows,
        "approval_batches": {"ordered_batches": batch_out},
        "global_approval_boundary": {
            "approval_artifact_only": True,
            "signed_approval_count": 0,
            "actual_activation_count": 0,
            "may_persist_approvals_now": False,
            "may_activate_sources_now": False,
            "may_write_database_rows_now": False,
            "may_scrape_now": False,
            "may_ingest_now": False,
            "may_call_external_apis_now": False,
            "may_create_ledger_actions_now": False,
            "requires_future_activation_command_dry_run": True,
            "requires_future_activation_sprint": True,
            "notes": gb_notes,
        },
        "risk_flags": risk_flags,
        "summary": _approval_summary(
            org_id=org_id,
            posture=posture,
            artifact_n=len(approval_rows),
            batch_n=len(batch_out),
            cond_n=cond_n,
        ),
        "recommended_review_interval_days": review_days,
    }
    return _json_safe(out)
