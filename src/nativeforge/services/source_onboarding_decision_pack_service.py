"""Sprint 38: deterministic Source Candidate Onboarding Decision Pack (review-only)."""

from __future__ import annotations

import json
from typing import Any

from nativeforge.domain.enums import OperatorDecisionSeverity
from nativeforge.services import source_candidate_registry_service as scr_svc

SCHEMA_VERSION = "nf_source_onboarding_decision_pack_v1"

_PRIORITY_RANK: dict[str, int] = {
    OperatorDecisionSeverity.critical.value: 0,
    OperatorDecisionSeverity.high.value: 1,
    OperatorDecisionSeverity.medium.value: 2,
    OperatorDecisionSeverity.low.value: 3,
    OperatorDecisionSeverity.info.value: 4,
}

_REVIEW_INTERVAL_DAYS: dict[str, int] = {
    "critical": 7,
    "weak": 14,
    "adequate": 30,
    "strong": 90,
}

_READINESS_TO_RECOMMENDATION: dict[str, str] = {
    "ready_for_review": "ready_for_operator_review",
    "needs_research": "needs_research",
    "legal_tos_review_required": "requires_legal_tos_review",
    "deferred": "defer_until_lane_gap_confirmed",
}

_ALL_BASE_CHECKS: tuple[str, ...] = (
    "confirm_public_access_or_official_source",
    "confirm_native_relevance_basis",
    "confirm_no_customer_data_required",
    "confirm_no_ai_training_or_sensitive_data_issue",
    "define_provenance_capture_plan",
    "define_dedupe_key_strategy",
    "define_freshness_check_cadence",
)


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _review_recommendation(registry_readiness: str) -> str:
    return _READINESS_TO_RECOMMENDATION.get(registry_readiness, "needs_research")


def _implies_scrape_or_portal_monitoring(
    cand: dict[str, Any],
) -> bool:
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


def _onboarding_readiness_score(
    cand: dict[str, Any],
    recommendation: str,
) -> int:
    pri = str(cand.get("priority") or OperatorDecisionSeverity.medium.value)
    base_map = {
        OperatorDecisionSeverity.critical.value: 58,
        OperatorDecisionSeverity.high.value: 54,
        OperatorDecisionSeverity.medium.value: 48,
        OperatorDecisionSeverity.low.value: 44,
        OperatorDecisionSeverity.info.value: 40,
    }
    s = int(base_map.get(pri, 46))
    if recommendation == "ready_for_operator_review":
        s += 22
    elif recommendation == "needs_research":
        s += 8
    elif recommendation == "requires_legal_tos_review":
        s += 4
    else:
        s -= 6
    lane = str(cand.get("lane") or "")
    if lane == "federal_native_specific":
        if recommendation != "requires_legal_tos_review":
            s += 10
    if lane == "general_broad_with_native_eligibility":
        s = min(s, 58)
        if _keywords_keyword_only_native(cand):
            s = min(s, 52)
    if lane in {
        "foundation_native_serving",
        "corporate_philanthropy",
        "university_research",
    }:
        s = min(s, 72)
    return max(0, min(100, s))


def _required_operator_checks(
    cand: dict[str, Any],
    recommendation: str,
) -> list[str]:
    checks: list[str] = []
    for c in _ALL_BASE_CHECKS:
        checks.append(c)
    lane = str(cand.get("lane") or "")
    st = str(cand.get("source_type") or "").lower()

    checks.append("confirm_update_frequency")

    if lane == "general_broad_with_native_eligibility":
        checks.append("confirm_human_review_required_for_broad_eligibility")

    if (
        recommendation == "requires_legal_tos_review"
        or _implies_scrape_or_portal_monitoring(cand)
    ):
        checks.append("confirm_terms_of_use_or_api_policy")
        checks.append("confirm_robots_or_access_policy_before_scraping_future")

    if lane in {
        "foundation_native_serving",
        "corporate_philanthropy",
        "university_research",
    } or st in {"foundation", "corporate", "university"}:
        if "confirm_terms_of_use_or_api_policy" not in checks:
            checks.append("confirm_terms_of_use_or_api_policy")
        checks.append("confirm_human_review_required_for_broad_eligibility")

    if recommendation == "needs_research":
        checks.append("confirm_terms_of_use_or_api_policy")

    # Dedupe preserve order
    seen: set[str] = set()
    out: list[str] = []
    for x in checks:
        if x not in seen:
            seen.add(x)
            out.append(x)
    return sorted(out)


def _approval_blockers(
    cand: dict[str, Any],
    recommendation: str,
) -> list[str]:
    lane = str(cand.get("lane") or "")
    out: list[str] = []
    if recommendation == "requires_legal_tos_review":
        out.append("legal_and_terms_of_use_not_confirmed")
    if lane == "general_broad_with_native_eligibility":
        out.append("tribal_eligibility_not_human_confirmed")
    if recommendation == "needs_research":
        out.append("publisher_fit_and_access_not_validated")
    if recommendation == "defer_until_lane_gap_confirmed":
        out.append("lane_planning_dependency_unresolved")
    return sorted(set(out))


def _suggested_validation_steps(
    cand: dict[str, Any],
    recommendation: str,
) -> list[str]:
    lane = str(cand.get("lane") or "")
    steps: list[str] = [
        "Verify publisher identity and official program scope (desk review only).",
        "Record Native relevance basis without implying eligibility confirmation.",
    ]
    if recommendation == "requires_legal_tos_review":
        steps.append(
            "Review publisher terms, robots/AUP, and API policy before any future crawl."
        )
    if lane == "general_broad_with_native_eligibility":
        steps.append(
            "Treat keyword Native mentions as review signals only—not eligibility proof."
        )
    if lane in {
        "foundation_native_serving",
        "corporate_philanthropy",
        "university_research",
    }:
        steps.append(
            "Research foundation/corporate/university program rules and geography constraints."
        )
    return steps


def _data_governance_notes(cand: dict[str, Any]) -> str:
    return (
        "Planning-only artifact: no customer payloads; no training-data assumptions; "
        "capture provenance if promoted later."
    )


def _tribal_sovereignty_notes(cand: dict[str, Any]) -> str:
    lane = str(cand.get("lane") or "")
    if lane == "tribal_government":
        return (
            "Respect tribal data sovereignty and publication norms; defer to nation-led "
            "policies for access."
        )
    return (
        "Native-first relevance must align with tribal governance context where applicable; "
        "do not infer tribal eligibility from keywords alone."
    )


def _candidate_review_row(
    cand: dict[str, Any],
    *,
    plan_overrepresented: set[str],
) -> dict[str, Any]:
    raw_ready = str(cand.get("onboarding_readiness") or "needs_research")
    recommendation = _review_recommendation(raw_ready)
    lane = str(cand.get("lane") or "")

    score = _onboarding_readiness_score(cand, recommendation)
    rationale_parts = [
        str(cand.get("rationale") or ""),
        (
            "Onboarding decision pack: review-only; no live ingestion; activation remains "
            "future-gated."
        ),
    ]
    if lane == "general_broad_with_native_eligibility":
        rationale_parts.insert(
            0,
            "Broad Native-eligible class—human review required; no confirmed eligibility.",
        )
    row = {
        "candidate_id": str(cand.get("candidate_id") or ""),
        "source_name": str(cand.get("source_name") or ""),
        "lane": lane,
        "source_type": str(cand.get("source_type") or ""),
        "priority": str(cand.get("priority") or ""),
        "review_recommendation": recommendation,
        "onboarding_readiness_score": score,
        "rationale": " ".join(rationale_parts).strip(),
        "required_operator_checks": _required_operator_checks(cand, recommendation),
        "approval_blockers": _approval_blockers(cand, recommendation),
        "suggested_validation_steps": _suggested_validation_steps(cand, recommendation),
        "data_governance_notes": _data_governance_notes(cand),
        "tribal_sovereignty_notes": _tribal_sovereignty_notes(cand),
        "no_live_ingestion_boundary": True,
        "can_become_active_source": False,
        "should_create_action": False,
    }
    # Overrepresented lane maintenance: annotate without deprioritizing federal_native_specific.
    if lane in plan_overrepresented and lane != "federal_native_specific":
        row["rationale"] = (
            row["rationale"]
            + " Maintenance or provenance-hardening sequencing—does not prioritize "
            "lane concentration expansion."
        )
    return _json_safe(row)


def _sort_candidate_ids_for_review(
    candidates: list[dict[str, Any]],
    reviews_by_id: dict[str, dict[str, Any]],
    *,
    overrepresented_lanes: set[str],
    rationale_text_by_id: dict[str, str],
) -> list[str]:
    def sort_key(cid: str) -> tuple[int, int, int, int, str]:
        rev = reviews_by_id.get(cid, {})
        lane = str(rev.get("lane") or "")
        fed = 0 if lane == "federal_native_specific" else 1
        pri = str(rev.get("priority") or "")
        pr = _PRIORITY_RANK.get(pri, 99)
        bal = rationale_text_by_id.get(cid, "")
        balancing = 1 if "Balancing diversification" in bal else 0
        over = (
            1
            if lane in overrepresented_lanes and lane != "federal_native_specific"
            else 0
        )
        return (fed, over, balancing, pr, cid)

    ids = [
        str(c.get("candidate_id") or "") for c in candidates if c.get("candidate_id")
    ]
    return sorted(ids, key=lambda i: sort_key(i))


def _recommended_batch_size(posture: str, candidate_n: int) -> int:
    if posture == "strong":
        return min(3, max(1, candidate_n))
    if posture == "critical":
        return min(4, max(1, candidate_n))
    if posture == "weak":
        return min(5, max(1, candidate_n))
    return min(6, max(1, candidate_n))


def _batch_review_plan(
    ordered_ids: list[str],
    reviews_by_id: dict[str, dict[str, Any]],
    *,
    posture: str,
    batch_size: int,
) -> list[dict[str, Any]]:
    if not ordered_ids or batch_size <= 0:
        return []
    batches: list[dict[str, Any]] = []
    bn = 0
    for i in range(0, len(ordered_ids), batch_size):
        chunk = ordered_ids[i : i + batch_size]
        lanes = sorted(
            {str(reviews_by_id[cid].get("lane") or "") for cid in chunk if cid}
        )
        pri = OperatorDecisionSeverity.medium.value
        if posture == "critical" and bn == 0:
            title = "Federal Native-specific led minimum viable onboarding review"
            rationale = (
                "Critical or empty-registry posture: start with a small federal "
                "Native-specific-led batch; staged diligence rather than mass onboarding."
            )
            pri = OperatorDecisionSeverity.high.value
        elif posture == "strong":
            title = "Maintenance verification batch (sequenced)"
            rationale = (
                "Strong posture: keep batches small and maintenance-focused—avoid urgent "
                "mass onboarding framing."
            )
            pri = OperatorDecisionSeverity.low.value
        else:
            title = f"Onboarding review batch {bn + 1} (sequenced)"
            rationale = (
                "Deterministic sequenced review batch—activation remains gated; no live "
                "ingestion in this sprint."
            )
        checks = sorted(
            {
                x
                for cid in chunk
                for x in (reviews_by_id.get(cid) or {}).get(
                    "required_operator_checks", []
                )
            }
        )
        batches.append(
            _json_safe(
                {
                    "batch_number": bn + 1,
                    "priority": pri,
                    "title": title,
                    "rationale": rationale,
                    "candidate_ids": list(chunk),
                    "focus_lanes": lanes,
                    "max_candidates": len(chunk),
                    "required_checks": checks,
                    "should_create_action": False,
                }
            )
        )
        bn += 1
    return batches


def _pack_risk_flags(
    candidates: list[dict[str, Any]],
    reviews: list[dict[str, Any]],
    *,
    posture: str,
    ready_n: int,
    legal_n: int,
    deferred_n: int,
    batch_size: int,
    high_pri_lane_unreviewed: bool,
) -> list[str]:
    flags: list[str] = []
    if ready_n == 0:
        flags.append("no_ready_candidates")
    if legal_n > 0:
        flags.append("legal_tos_review_required")
    if any(
        str(c.get("lane") or "") == "federal_native_relevant_broad" for c in candidates
    ):
        flags.append("public_access_unclear")
    if deferred_n > 0:
        flags.append("source_freshness_strategy_missing")
    flags.append("provenance_plan_required")
    if any(
        str(r.get("lane") or "") == "general_broad_with_native_eligibility"
        for r in reviews
    ):
        flags.append("broad_eligibility_review_required")
    if any(_keywords_keyword_only_native(c) for c in candidates):
        flags.append("keyword_only_review_required")
    if high_pri_lane_unreviewed:
        flags.append("high_priority_lane_unreviewed")
    if batch_size > 8:
        flags.append("batch_size_too_large")
    if posture == "strong" and batch_size > 4:
        flags.append("batch_size_too_large")
    return sorted(set(flags))


def _activation_notes() -> str:
    return (
        "This sprint emits planning payloads only: no activation, no ingestion connectors, "
        "no scraping, no external API calls, no registry persistence from this pack."
    )


def _pack_summary(
    *,
    org_id: str,
    posture: str,
    candidate_n: int,
    batch_n: int,
) -> str:
    if posture == "strong":
        return (
            f"Organization {org_id}: onboarding decision pack ({candidate_n} candidates, "
            f"{batch_n} maintenance-style batches)—human approval required before any future "
            "activation; no live ingestion."
        )
    if posture == "critical":
        return (
            f"Organization {org_id}: minimum viable onboarding review package ({candidate_n} "
            "candidates)—federal Native-specific-led sequencing; staged review only."
        )
    return (
        f"Organization {org_id}: onboarding review package for {candidate_n} deterministic "
        f"candidates across {batch_n} batches—activation blocked pending human approval."
    )


def build_source_onboarding_decision_pack(
    source_quality: dict[str, Any],
) -> dict[str, Any]:
    """Return nf_source_onboarding_decision_pack_v1 from source_quality (+ embedded registry)."""
    sq = dict(source_quality)
    reg = sq.get("source_candidate_registry")
    if not isinstance(reg, dict) or not reg.get("candidate_sources"):
        reg = scr_svc.build_source_candidate_registry(sq)

    candidates: list[dict[str, Any]] = list(reg.get("candidate_sources") or [])
    posture = str(sq.get("posture") or "adequate")
    dqs = int(sq.get("data_quality_score") or 0)
    active_n = int((sq.get("source_counts") or {}).get("active") or 0)
    org_id = str(sq.get("organization_id") or "")
    gen_at = str(
        (reg.get("organization_scope") or {}).get("generated_at")
        or sq.get("generated_at")
        or ""
    )

    plan = sq.get("source_coverage_plan") or {}
    overrepresented_lanes = {
        str(x.get("lane") or "")
        for x in (plan.get("priority_lanes") or [])
        if str(x.get("status") or "") == "overrepresented"
    }
    overrepresented_lanes.discard("")

    rationale_by_id = {
        str(c.get("candidate_id") or ""): str(c.get("rationale") or "")
        for c in candidates
    }

    reviews: list[dict[str, Any]] = []
    reviews_by_id: dict[str, dict[str, Any]] = {}
    for c in candidates:
        row = _candidate_review_row(c, plan_overrepresented=overrepresented_lanes)
        reviews.append(row)
        reviews_by_id[row["candidate_id"]] = row

    ready_n = sum(
        1
        for r in reviews
        if r.get("review_recommendation") == "ready_for_operator_review"
    )
    legal_n = sum(
        1
        for r in reviews
        if r.get("review_recommendation") == "requires_legal_tos_review"
    )
    deferred_n = sum(
        1
        for r in reviews
        if r.get("review_recommendation") == "defer_until_lane_gap_confirmed"
    )

    batch_size = _recommended_batch_size(posture, len(candidates))
    ordered_ids = _sort_candidate_ids_for_review(
        candidates,
        reviews_by_id,
        overrepresented_lanes=overrepresented_lanes,
        rationale_text_by_id=rationale_by_id,
    )
    batches = _batch_review_plan(
        ordered_ids,
        reviews_by_id,
        posture=posture,
        batch_size=batch_size,
    )

    has_federal_native_specific = any(
        str(c.get("lane") or "") == "federal_native_specific" for c in candidates
    )
    high_pri_lane_unreviewed = posture in {"weak", "critical"} and (
        not has_federal_native_specific
    )

    risk_flags = _pack_risk_flags(
        candidates,
        reviews,
        posture=posture,
        ready_n=ready_n,
        legal_n=legal_n,
        deferred_n=deferred_n,
        batch_size=batch_size,
        high_pri_lane_unreviewed=high_pri_lane_unreviewed,
    )

    review_days = int(_REVIEW_INTERVAL_DAYS.get(posture, 30))

    out: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "organization_scope": {
            "organization_id": org_id,
            "generated_at": gen_at,
        },
        "decision_posture": {
            "source_quality_posture": posture,
            "data_quality_score": dqs,
            "active_source_count": active_n,
            "candidate_count": len(candidates),
            "ready_for_review_count": ready_n,
            "legal_tos_review_count": legal_n,
            "deferred_count": deferred_n,
            "recommended_batch_size": batch_size,
        },
        "candidate_reviews": reviews,
        "batch_review_plan": batches,
        "activation_boundary": {
            "may_activate_sources": False,
            "requires_human_approval": True,
            "requires_tos_review_for_scraped_sources": True,
            "requires_source_owner_or_public_access_confirmation": True,
            "requires_freshness_strategy": True,
            "requires_provenance_plan": True,
            "requires_dedupe_strategy": True,
            "notes": _activation_notes(),
        },
        "risk_flags": risk_flags,
        "summary": _pack_summary(
            org_id=org_id,
            posture=posture,
            candidate_n=len(candidates),
            batch_n=len(batches),
        ),
        "recommended_review_interval_days": review_days,
    }
    return _json_safe(out)
