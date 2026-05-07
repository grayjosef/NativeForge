"""Sprint 39: deterministic Source Activation Readiness Contract (planning-only)."""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services import source_onboarding_decision_pack_service as sodp_svc

SCHEMA_VERSION = "nf_source_activation_readiness_contract_v1"

_REVIEW_INTERVAL_DAYS: dict[str, int] = {
    "critical": 7,
    "weak": 14,
    "adequate": 30,
    "strong": 90,
}

_STATUS_RANK: dict[str, int] = {
    "blocked": 0,
    "not_ready": 1,
    "review_ready": 2,
    "conditionally_ready": 3,
}

_RANK_TO_STATUS: dict[int, str] = {v: k for k, v in _STATUS_RANK.items()}


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _implies_scrape_or_portal_monitoring(cand: dict[str, Any]) -> bool:
    st = str(cand.get("source_type") or "").lower()
    tgt = str(cand.get("suggested_url_pattern_or_search_target") or "").lower()
    if st in {"corporate", "foundation", "private"}:
        return "search" in tgt or "portal" in tgt
    lane = str(cand.get("lane") or "")
    if lane == "federal_native_relevant_broad":
        return True
    return False


def _keywords_keyword_only_native(cand: dict[str, Any]) -> bool:
    lane = str(cand.get("lane") or "")
    if lane != "general_broad_with_native_eligibility":
        return False
    rel = str(cand.get("expected_native_relevance") or "").lower()
    return (
        "keyword" in rel or "not_keyword_confirmation" in rel or "catalog_review" in rel
    )


def _is_philanthropy_or_uni_lane(lane: str) -> bool:
    return lane in {
        "foundation_native_serving",
        "corporate_philanthropy",
        "university_research",
    }


def _derive_activation_status(
    review: dict[str, Any],
    raw_cand: dict[str, Any],
    *,
    overrepresented_lanes: set[str],
) -> str:
    rec = str(review.get("review_recommendation") or "")
    lane = str(review.get("lane") or "")
    if lane == "general_broad_with_native_eligibility":
        if _keywords_keyword_only_native(raw_cand):
            return "not_ready"
        # Broad registry rows use needs_research as the staged human-review track.
        return "review_ready"
    if rec == "defer_until_lane_gap_confirmed":
        return "blocked"
    if rec == "requires_legal_tos_review":
        return "blocked"
    if rec == "needs_research":
        return "blocked"
    if rec != "ready_for_operator_review":
        return "blocked"
    if _is_philanthropy_or_uni_lane(lane) or str(
        raw_cand.get("source_type") or ""
    ).lower() in {"foundation", "corporate", "university"}:
        return "review_ready"
    if lane == "federal_native_specific":
        if lane in overrepresented_lanes:
            return "review_ready"
        return "conditionally_ready"
    return "review_ready"


def _activation_readiness_score(
    review: dict[str, Any],
    activation_status: str,
) -> int:
    base = int(review.get("onboarding_readiness_score") or 0)
    if activation_status == "conditionally_ready":
        return max(0, min(100, base))
    if activation_status == "blocked":
        return max(0, min(100, min(base, 72)))
    if activation_status == "not_ready":
        return max(0, min(100, min(base, 55)))
    return max(0, min(100, base))


def _required_approvals(
    review: dict[str, Any],
    raw_cand: dict[str, Any],
    *,
    activation_status: str,
    legal_tos: bool,
    robots_review: bool,
) -> list[str]:
    lane = str(review.get("lane") or "")
    out: list[str] = [
        "operator_source_review_approval",
        "provenance_plan_approval",
        "freshness_strategy_approval",
        "dedupe_strategy_approval",
        "native_relevance_basis_approval",
        "source_owner_or_public_access_approval",
        "no_customer_data_required_confirmation",
        "no_sensitive_data_or_ai_training_issue_confirmation",
    ]
    if lane == "general_broad_with_native_eligibility":
        out.append("broad_eligibility_human_review_approval")
    if legal_tos or activation_status == "blocked":
        out.append("legal_tos_review_approval")
    if robots_review:
        out.append("legal_tos_review_approval")
    return sorted(set(out))


def _required_evidence(
    review: dict[str, Any],
    raw_cand: dict[str, Any],
    *,
    legal_tos: bool,
) -> list[str]:
    lane = str(review.get("lane") or "")
    ev: list[str] = [
        "publisher_or_program_identity_record",
        "native_relevance_basis_record",
        "capture_and_citation_plan_record",
    ]
    if legal_tos:
        ev.append("terms_robots_or_access_policy_desk_review_record")
    if lane == "general_broad_with_native_eligibility":
        ev.append("broad_eligibility_human_review_record_not_keyword_proof")
    if _is_philanthropy_or_uni_lane(lane):
        ev.append("foundation_corporate_or_university_program_rules_research_record")
    return sorted(set(ev))


def _legal_native_contracts(
    review: dict[str, Any],
    raw_cand: dict[str, Any],
    *,
    recommendation: str,
) -> tuple[dict[str, bool], dict[str, bool]]:
    lane = str(review.get("lane") or "")
    legal_tos = recommendation == "requires_legal_tos_review" or (
        _is_philanthropy_or_uni_lane(lane)
        or str(raw_cand.get("source_type") or "").lower()
        in {"foundation", "corporate", "university"}
    )
    robots_review = (
        _implies_scrape_or_portal_monitoring(raw_cand)
        or recommendation == "requires_legal_tos_review"
        or lane == "federal_native_relevant_broad"
    )
    legal_block = {
        "tos_review_required": bool(legal_tos),
        "robots_or_access_policy_review_required": bool(robots_review),
        "public_access_confirmation_required": True,
        "no_scraping_until_approved": True,
    }
    keyword_only = _keywords_keyword_only_native(raw_cand)
    native_block = {
        "native_relevance_basis_required": True,
        "broad_eligibility_human_review_required": lane
        == "general_broad_with_native_eligibility",
        "keyword_only_not_confirmed_eligible": bool(keyword_only),
        "tribal_specificity_notes_required": True,
    }
    return legal_block, native_block


def _batch_status(statuses: list[str]) -> str:
    if not statuses:
        return "not_ready"
    worst = min(_STATUS_RANK.get(s, 1) for s in statuses)
    return _RANK_TO_STATUS.get(worst, "not_ready")


def _contract_summary(
    *,
    org_id: str,
    posture: str,
    candidate_n: int,
    batch_n: int,
    cond_n: int,
) -> str:
    if posture == "strong":
        pre = (
            f"Organization {org_id}: activation readiness contract "
            f"({candidate_n} candidates, {batch_n} maintenance batches). "
        )
        post = (
            "Future activation remains human-gated; conservative sequencing and "
            "provenance hardening rather than urgent expansion framing."
        )
        return pre + post
    if posture == "critical":
        pre = (
            f"Organization {org_id}: activation readiness contract "
            f"({candidate_n} candidates). "
        )
        post = (
            "Critical or sparse posture: prioritize federal Native-specific diligence "
            "first; "
            f"{cond_n} candidate(s) marked conditionally_ready for future governance "
            "only—no live activation in this sprint."
        )
        return pre + post
    pre = (
        f"Organization {org_id}: activation readiness contract for "
        f"{candidate_n} candidates across {batch_n} batches—human approval and "
        f"a future activation sprint "
    )
    post = "are required before any promotion to active opportunity sources."
    return pre + post


def _risk_flags_contract(
    contracts: list[dict[str, Any]],
    *,
    cond_n: int,
    blocked_high: bool,
) -> list[str]:
    flags: list[str] = []
    if cond_n == 0:
        flags.append("no_activation_ready_candidates")
    flags.append("human_approval_required")
    if any(
        c["legal_tos_contract"]["tos_review_required"]
        or c["legal_tos_contract"]["robots_or_access_policy_review_required"]
        for c in contracts
    ):
        flags.append("legal_tos_review_required")
    flags.append("provenance_plan_required")
    flags.append("freshness_strategy_required")
    flags.append("dedupe_strategy_required")
    if any(
        c["native_relevance_contract"]["broad_eligibility_human_review_required"]
        for c in contracts
    ):
        flags.append("broad_eligibility_review_required")
    kw_any = any(
        c["native_relevance_contract"]["keyword_only_not_confirmed_eligible"]
        for c in contracts
    )
    if kw_any:
        flags.append("keyword_only_review_required")
    fed_broad = any(
        str(c.get("lane") or "") == "federal_native_relevant_broad" for c in contracts
    )
    if fed_broad:
        flags.append("public_access_unclear")
    flags.append("activation_not_allowed_in_this_sprint")
    if blocked_high:
        flags.append("high_priority_candidates_blocked")
    return sorted(set(flags))


def build_source_activation_readiness_contract(
    source_quality: dict[str, Any],
) -> dict[str, Any]:
    """Return nf_source_activation_readiness_contract_v1 from source_quality."""
    sq = dict(source_quality)
    pack = sq.get("source_onboarding_decision_pack")
    pack_ok = isinstance(pack, dict) and (
        pack.get("schema_version") == sodp_svc.SCHEMA_VERSION
    )
    if not pack_ok:
        pack = sodp_svc.build_source_onboarding_decision_pack(sq)

    reg = sq.get("source_candidate_registry")
    if not isinstance(reg, dict):
        reg = {}
    raw_by_id: dict[str, dict[str, Any]] = {
        str(c.get("candidate_id") or ""): dict(c)
        for c in (reg.get("candidate_sources") or [])
        if c.get("candidate_id")
    }

    plan = sq.get("source_coverage_plan") or {}
    overrepresented_lanes = {
        str(x.get("lane") or "")
        for x in (plan.get("priority_lanes") or [])
        if str(x.get("status") or "") == "overrepresented"
    }
    overrepresented_lanes.discard("")

    dp = pack.get("decision_posture") or {}
    posture = str(sq.get("posture") or dp.get("source_quality_posture") or "adequate")
    dqs = int(sq.get("data_quality_score") or dp.get("data_quality_score") or 0)
    src_counts = sq.get("source_counts") or {}
    active_n = int(src_counts.get("active") or dp.get("active_source_count") or 0)
    org_id = str(sq.get("organization_id") or "")
    gen_at = str(
        (pack.get("organization_scope") or {}).get("generated_at")
        or sq.get("generated_at")
        or ""
    )

    activation_contracts: list[dict[str, Any]] = []
    for review in pack.get("candidate_reviews") or []:
        cid = str(review.get("candidate_id") or "")
        raw_cand = raw_by_id.get(cid, {})
        rec = str(review.get("review_recommendation") or "")
        act_status = _derive_activation_status(
            review, raw_cand, overrepresented_lanes=overrepresented_lanes
        )
        rscore = _activation_readiness_score(review, act_status)
        legal_c, native_c = _legal_native_contracts(
            review, raw_cand, recommendation=rec
        )
        robots_rev = bool(legal_c["robots_or_access_policy_review_required"])
        approvals = _required_approvals(
            review,
            raw_cand,
            activation_status=act_status,
            legal_tos=bool(legal_c["tos_review_required"]),
            robots_review=robots_rev,
        )
        evidence = _required_evidence(
            review, raw_cand, legal_tos=bool(legal_c["tos_review_required"])
        )
        arc_tail = (
            "Activation readiness contract: planning-only; future human-approved "
            "activation sprint required; no registry activation or ingestion in "
            "this sprint."
        )
        rationale_parts = [str(review.get("rationale") or ""), arc_tail]
        readiness_rationale = " ".join(rationale_parts).strip()
        pri = str(review.get("priority") or "")

        row = {
            "candidate_id": cid,
            "source_name": str(review.get("source_name") or ""),
            "lane": str(review.get("lane") or ""),
            "source_type": str(review.get("source_type") or ""),
            "priority": pri,
            "activation_status": act_status,
            "readiness_score": rscore,
            "readiness_rationale": readiness_rationale,
            "required_approvals": approvals,
            "required_evidence": evidence,
            "required_operator_checks": list(
                review.get("required_operator_checks") or []
            ),
            "activation_blockers": list(review.get("approval_blockers") or []),
            "provenance_contract": {
                "source_owner_or_publisher_required": True,
                "source_url_or_search_target_required": True,
                "capture_method_required": True,
                "citation_or_evidence_required": True,
                "operator_notes_required": True,
            },
            "freshness_contract": {
                "update_frequency_required": True,
                "freshness_check_cadence_required": True,
                "stale_threshold_required": True,
                "failure_handling_required": True,
            },
            "dedupe_contract": {
                "duplicate_key_strategy_required": True,
                "overlap_review_required": True,
                "source_priority_rules_required": True,
            },
            "legal_tos_contract": legal_c,
            "native_relevance_contract": native_c,
            "activation_boundary": {
                "may_activate_source_now": False,
                "may_write_active_source_now": False,
                "requires_human_approval": True,
                "requires_future_activation_sprint": True,
            },
            "can_become_active_source": False,
            "should_create_action": False,
        }
        activation_contracts.append(_json_safe(row))

    by_id_status = {
        c["candidate_id"]: c["activation_status"] for c in activation_contracts
    }
    blocked_high = any(
        str(c.get("priority") or "") in {"critical", "high"}
        and c.get("activation_status") == "blocked"
        for c in activation_contracts
    )

    batch_rows: list[dict[str, Any]] = []
    for b in pack.get("batch_review_plan") or []:
        cids = list(b.get("candidate_ids") or [])
        st_list = [by_id_status.get(cid, "not_ready") for cid in cids]
        batch_rows.append(
            _json_safe(
                {
                    "batch_number": int(b.get("batch_number") or 0),
                    "priority": str(b.get("priority") or ""),
                    "title": str(b.get("title") or ""),
                    "rationale": str(b.get("rationale") or ""),
                    "candidate_ids": cids,
                    "focus_lanes": list(b.get("focus_lanes") or []),
                    "batch_status": _batch_status(st_list),
                    "required_batch_checks": sorted(
                        set(b.get("required_checks") or [])
                    ),
                    "should_create_action": False,
                }
            )
        )

    review_ready_n = sum(
        1 for c in activation_contracts if c["activation_status"] == "review_ready"
    )
    cond_n = sum(
        1
        for c in activation_contracts
        if c["activation_status"] == "conditionally_ready"
    )
    blocked_n = sum(
        1 for c in activation_contracts if c["activation_status"] == "blocked"
    )
    legal_tos_n = sum(
        1
        for c in activation_contracts
        if c["legal_tos_contract"]["tos_review_required"]
    )

    risk_flags = _risk_flags_contract(
        activation_contracts,
        cond_n=cond_n,
        blocked_high=blocked_high,
    )

    review_days = int(_REVIEW_INTERVAL_DAYS.get(posture, 30))

    out: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "organization_scope": {
            "organization_id": org_id,
            "generated_at": gen_at,
        },
        "contract_posture": {
            "source_quality_posture": posture,
            "data_quality_score": dqs,
            "active_source_count": active_n,
            "candidate_count": len(activation_contracts),
            "review_ready_count": review_ready_n,
            "activation_ready_count": cond_n,
            "blocked_count": blocked_n,
            "legal_tos_required_count": legal_tos_n,
            "human_approval_required_count": len(activation_contracts),
        },
        "activation_contracts": activation_contracts,
        "batch_activation_readiness": {
            "ordered_batches": batch_rows,
        },
        "global_activation_boundary": {
            "may_activate_sources_now": False,
            "may_write_database_rows_now": False,
            "may_scrape_now": False,
            "may_call_external_apis_now": False,
            "may_create_ledger_actions_now": False,
            "requires_human_approval": True,
            "requires_future_activation_sprint": True,
            "notes": (
                "Sprint 39 activation readiness contract is planning-only: no "
                "activation, no candidate promotion, no ingestion connectors, no "
                "scraping, no external API calls, and no operator ledger actions from "
                "this layer."
            ),
        },
        "risk_flags": risk_flags,
        "summary": _contract_summary(
            org_id=org_id,
            posture=posture,
            candidate_n=len(activation_contracts),
            batch_n=len(batch_rows),
            cond_n=cond_n,
        ),
        "recommended_review_interval_days": review_days,
    }
    return _json_safe(out)
