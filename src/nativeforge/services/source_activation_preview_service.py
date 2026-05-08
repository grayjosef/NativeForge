"""Sprint 40: deterministic Human-Approved Source Activation Preview (dry-run only)."""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services import (
    source_activation_readiness_contract_service as sarc_svc,
)

SCHEMA_VERSION = "nf_source_activation_preview_v1"

_REVIEW_INTERVAL_DAYS: dict[str, int] = {
    "critical": 7,
    "weak": 14,
    "adequate": 30,
    "strong": 90,
}

_PREVIEW_STATUS_RANK: dict[str, int] = {
    "preview_only_blocked": 0,
    "preview_only_not_ready": 1,
    "preview_only_review_required": 2,
    "preview_only_conditionally_ready": 3,
}

_PREVIEW_RANK_TO_STATUS: dict[int, str] = {
    v: k for k, v in _PREVIEW_STATUS_RANK.items()
}


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _activation_to_preview_status(activation_status: str) -> str:
    return {
        "conditionally_ready": "preview_only_conditionally_ready",
        "blocked": "preview_only_blocked",
        "not_ready": "preview_only_not_ready",
        "review_ready": "preview_only_review_required",
    }.get(activation_status, "preview_only_not_ready")


def _implies_api_use(raw: dict[str, Any]) -> bool:
    tgt = str(raw.get("suggested_url_pattern_or_search_target") or "").lower()
    name = str(raw.get("source_name") or "").lower()
    st = str(raw.get("source_type") or "").lower()
    return "api" in tgt or st == "api" or " api " in name or name.endswith(" api")


def _implies_portal(raw: dict[str, Any]) -> bool:
    tgt = str(raw.get("suggested_url_pattern_or_search_target") or "").lower()
    return "portal" in tgt


def _proposed_collection_method(
    raw: dict[str, Any],
    *,
    lane: str,
    source_type: str,
) -> str:
    st = source_type.lower()
    ln = lane
    if _implies_api_use(raw):
        return "api_review_future"
    if _implies_portal(raw):
        return "portal_review_future"
    if ln == "federal_native_relevant_broad":
        return "public_notice_monitoring_future"
    if ln == "federal_native_specific" and st == "federal":
        return "official_page_monitoring_future"
    if st in {"tribal", "federal"}:
        return "official_page_monitoring_future"
    if st in {"state", "local", "regional"}:
        return "public_notice_monitoring_future"
    if st in {"foundation", "corporate", "university", "private"}:
        return "manual_review_only"
    return "manual_review_only"


def _default_update_frequency(raw: dict[str, Any], lane: str) -> str:
    v = str(raw.get("expected_update_frequency") or "").strip()
    if v:
        return v
    if lane == "federal_native_specific":
        return "weekly_to_monthly_operator_basis"
    if lane == "federal_native_relevant_broad":
        return "biweekly_to_quarterly_notice_basis"
    return "monthly_review_basis"


def _freshness_cadence_days(lane: str, source_type: str) -> int:
    st = source_type.lower()
    if lane == "federal_native_specific":
        return 7
    if lane == "federal_native_relevant_broad":
        return 14
    if lane == "general_broad_with_native_eligibility":
        return 30
    if st in {"foundation", "corporate", "university"}:
        return 30
    return 14


def _stale_threshold_days(cadence: int) -> int:
    return int(min(120, max(cadence + 7, cadence * 2 + 1)))


def _dedupe_key_strategy(lane: str, candidate_id: str, source_type: str) -> str:
    return (
        f"deterministic_dedupe_v1:lane={lane}:type={source_type.lower()}:"
        f"anchor={candidate_id[:32]}"
    )


def _provenance_fields(lane: str) -> list[str]:
    base = [
        "canonical_target",
        "capture_context_note",
        "operator_review_reference",
        "publisher_identity",
    ]
    if lane == "general_broad_with_native_eligibility":
        base.append("broad_eligibility_review_anchor")
    return sorted(set(base))


def _native_relevance_basis(raw: dict[str, Any], lane: str) -> str:
    rel = str(raw.get("expected_native_relevance") or "").strip()
    if rel:
        return rel
    return f"lane_native_relevance_basis:{lane}"


def _batch_preview_status(statuses: list[str]) -> str:
    if not statuses:
        return "preview_only_not_ready"
    worst = min(_PREVIEW_STATUS_RANK.get(s, 1) for s in statuses)
    return _PREVIEW_RANK_TO_STATUS.get(worst, "preview_only_not_ready")


def _preview_summary(
    *,
    org_id: str,
    posture: str,
    preview_n: int,
    batch_n: int,
    cond_n: int,
) -> str:
    tail = (
        "Sprint 40 activation preview is dry-run only: no activation, no database "
        "writes, no ingestion, no scraping, no external APIs, and no operator "
        "ledger actions; human approval and a future activation sprint remain "
        "required before any active opportunity source rows may be created."
    )
    if posture == "strong":
        return (
            f"Organization {org_id}: human-approved activation preview "
            f"({preview_n} candidates, {batch_n} preview batches). "
            "Strong posture: conservative maintenance-oriented sequencing and "
            "hardening language rather than urgent activation framing. " + tail
        )
    if posture == "critical":
        return (
            f"Organization {org_id}: activation preview ({preview_n} candidates) "
            "with federal Native-specific-led first-batch emphasis for critical or "
            f"sparse posture; {cond_n} preview row(s) marked preview_only_"
            f"conditionally_ready as future governance signals only. " + tail
        )
    return (
        f"Organization {org_id}: activation preview for {preview_n} candidates "
        f"across {batch_n} ordered preview batches—reviewable proposed fields only. "
        + tail
    )


def _preview_risk_flags(
    *,
    cond_n: int,
    blocked_n: int,
    contracts: list[dict[str, Any]],
) -> list[str]:
    flags = [
        "preview_only_no_activation",
        "no_actual_activation_performed",
        "human_approval_required",
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
        c.get("native_relevance_contract", {}).get(
            "keyword_only_not_confirmed_eligible"
        )
        for c in contracts
    ):
        flags.append("keyword_only_review_required")
    if any(
        str(c.get("lane") or "") == "federal_native_relevant_broad" for c in contracts
    ):
        flags.append("public_access_unclear")
    if blocked_n > 0:
        flags.append("blocked_candidates_present")
    if cond_n == 0:
        flags.append("no_conditionally_ready_candidates")
    return sorted(set(flags))


def build_source_activation_preview(source_quality: dict[str, Any]) -> dict[str, Any]:
    """Return nf_source_activation_preview_v1 from source_quality (dry-run only)."""
    sq = dict(source_quality)
    arc = sq.get("source_activation_readiness_contract")
    if (
        not isinstance(arc, dict)
        or arc.get("schema_version") != sarc_svc.SCHEMA_VERSION
    ):
        arc = sarc_svc.build_source_activation_readiness_contract(sq)

    reg = sq.get("source_candidate_registry")
    if not isinstance(reg, dict):
        reg = {}
    raw_by_id: dict[str, dict[str, Any]] = {
        str(c.get("candidate_id") or ""): dict(c)
        for c in (reg.get("candidate_sources") or [])
        if c.get("candidate_id")
    }

    pack = sq.get("source_onboarding_decision_pack") or {}
    dp = pack.get("decision_posture") or {}
    posture = str(sq.get("posture") or dp.get("source_quality_posture") or "adequate")
    dqs = int(sq.get("data_quality_score") or dp.get("data_quality_score") or 0)
    src_counts = sq.get("source_counts") or {}
    active_n = int(src_counts.get("active") or dp.get("active_source_count") or 0)
    org_id = str(sq.get("organization_id") or "")
    gen_at = str(
        (arc.get("organization_scope") or {}).get("generated_at")
        or (pack.get("organization_scope") or {}).get("generated_at")
        or sq.get("generated_at")
        or ""
    )

    contracts: list[dict[str, Any]] = list(arc.get("activation_contracts") or [])
    activation_previews: list[dict[str, Any]] = []
    by_id_preview: dict[str, str] = {}

    preview_tail = (
        "Operator review notes: Sprint 40 preview-only row—proposed fields are "
        "not persisted and do not authorize activation."
    )

    for c in contracts:
        cid = str(c.get("candidate_id") or "")
        raw = raw_by_id.get(cid, {})
        lane = str(c.get("lane") or "")
        st = str(c.get("source_type") or "")
        name = str(c.get("source_name") or "")
        pri = str(c.get("priority") or "")
        act = str(c.get("activation_status") or "not_ready")
        pv_st = _activation_to_preview_status(act)
        by_id_preview[cid] = pv_st

        cadence = _freshness_cadence_days(lane, st)
        proposed = {
            "proposed_name": name,
            "proposed_source_type": st,
            "proposed_lane": lane,
            "proposed_collection_method": _proposed_collection_method(
                raw, lane=lane, source_type=st
            ),
            "proposed_update_frequency": _default_update_frequency(raw, lane),
            "proposed_freshness_cadence_days": cadence,
            "proposed_stale_threshold_days": _stale_threshold_days(cadence),
            "proposed_dedupe_key_strategy": _dedupe_key_strategy(lane, cid, st),
            "proposed_provenance_fields": _provenance_fields(lane),
            "proposed_native_relevance_basis": _native_relevance_basis(raw, lane),
            "proposed_human_review_required": True,
            "proposed_activation_mode": "future_human_approved_only",
        }
        rationale = str(c.get("readiness_rationale") or "")
        op_notes = (rationale + " " + preview_tail).strip()

        row: dict[str, Any] = {
            "candidate_id": cid,
            "source_name": name,
            "lane": lane,
            "source_type": st,
            "priority": pri,
            "source_activation_preview_status": pv_st,
            "proposed_active_source_record": proposed,
            "remaining_required_approvals": sorted(
                set(str(x) for x in (c.get("required_approvals") or []))
            ),
            "missing_required_evidence": sorted(
                set(str(x) for x in (c.get("required_evidence") or []))
            ),
            "activation_blockers": list(c.get("activation_blockers") or []),
            "operator_review_notes": op_notes,
            "dry_run_only": True,
            "may_activate_source_now": False,
            "may_write_active_source_now": False,
            "may_write_database_rows_now": False,
            "requires_future_activation_sprint": True,
            "requires_human_approval": True,
            "can_become_active_source": False,
            "should_create_action": False,
        }
        activation_previews.append(_json_safe(row))

    batch_rows: list[dict[str, Any]] = []
    for b in pack.get("batch_review_plan") or []:
        cids = list(b.get("candidate_ids") or [])
        st_list = [by_id_preview.get(cid, "preview_only_not_ready") for cid in cids]
        batch_rows.append(
            _json_safe(
                {
                    "batch_number": int(b.get("batch_number") or 0),
                    "priority": str(b.get("priority") or ""),
                    "title": str(b.get("title") or ""),
                    "rationale": str(b.get("rationale") or ""),
                    "candidate_ids": cids,
                    "focus_lanes": list(b.get("focus_lanes") or []),
                    "preview_batch_status": _batch_preview_status(st_list),
                    "required_batch_approvals": sorted(
                        {
                            "operator_batch_preview_review",
                            "evidence_and_approval_alignment_check",
                        }
                        | {str(x) for x in (b.get("required_checks") or [])}
                    ),
                    "dry_run_only": True,
                    "should_create_action": False,
                }
            )
        )

    cond_n = sum(
        1
        for p in activation_previews
        if p["source_activation_preview_status"] == "preview_only_conditionally_ready"
    )
    blocked_n = sum(
        1
        for p in activation_previews
        if p["source_activation_preview_status"] == "preview_only_blocked"
    )
    not_ready_n = sum(
        1
        for p in activation_previews
        if p["source_activation_preview_status"] == "preview_only_not_ready"
    )
    review_req_n = sum(
        1
        for p in activation_previews
        if p["source_activation_preview_status"] == "preview_only_review_required"
    )
    legal_tos_n = int(
        (arc.get("contract_posture") or {}).get("legal_tos_required_count") or 0
    )
    proposed_activation_n = cond_n + review_req_n

    risk_flags = _preview_risk_flags(
        cond_n=cond_n,
        blocked_n=blocked_n,
        contracts=contracts,
    )

    review_days = int(_REVIEW_INTERVAL_DAYS.get(posture, 30))

    out: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "organization_scope": {
            "organization_id": org_id,
            "generated_at": gen_at,
        },
        "preview_posture": {
            "source_quality_posture": posture,
            "data_quality_score": dqs,
            "active_source_count": active_n,
            "candidate_count": len(contracts),
            "preview_candidate_count": len(activation_previews),
            "conditionally_ready_count": cond_n,
            "blocked_count": blocked_n,
            "not_ready_count": not_ready_n,
            "human_approval_required_count": len(activation_previews),
            "legal_tos_required_count": legal_tos_n,
            "proposed_activation_count": proposed_activation_n,
            "actual_activation_count": 0,
        },
        "activation_previews": activation_previews,
        "activation_preview_batches": {"ordered_batches": batch_rows},
        "global_preview_boundary": {
            "preview_only": True,
            "actual_activation_count": 0,
            "may_activate_sources_now": False,
            "may_write_database_rows_now": False,
            "may_scrape_now": False,
            "may_ingest_now": False,
            "may_call_external_apis_now": False,
            "may_create_ledger_actions_now": False,
            "requires_human_approval": True,
            "requires_future_activation_sprint": True,
            "notes": (
                "Sprint 40 activation preview is preview-only: no activation, no "
                "promotion to active opportunity sources, no database writes for "
                "activation, no scraping, no ingestion, no external API calls, and "
                "no operator ledger actions from this layer."
            ),
        },
        "risk_flags": risk_flags,
        "summary": _preview_summary(
            org_id=org_id,
            posture=posture,
            preview_n=len(activation_previews),
            batch_n=len(batch_rows),
            cond_n=cond_n,
        ),
        "recommended_review_interval_days": review_days,
    }
    return _json_safe(out)
