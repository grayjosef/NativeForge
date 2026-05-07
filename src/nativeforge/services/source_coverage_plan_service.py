"""Sprint 36: deterministic Source Coverage Plan from calibrated source_quality payloads."""

from __future__ import annotations

import json
from typing import Any

from nativeforge.domain.enums import OperatorDecisionSeverity

SCHEMA_VERSION = "nf_source_coverage_plan_v1"

# Keep aligned with discovery_source_quality_service.NATIVE_PRIORITY_LANES (doctrine lanes).
_PLAN_LANES: tuple[str, ...] = (
    "federal_native_specific",
    "federal_native_relevant_broad",
    "tribal_government",
    "tribal_college",
    "native_nonprofit",
    "alaska_native",
    "native_hawaiian",
    "state_local_native_relevant",
    "foundation_native_serving",
    "corporate_philanthropy",
    "university_research",
    "general_broad_with_native_eligibility",
)

_PHILANTHROPY_LANES: tuple[str, ...] = (
    "foundation_native_serving",
    "corporate_philanthropy",
)

_STRONG_POSTURE_PRIORITY_CAP = OperatorDecisionSeverity.medium.value

_PRIORITY_ORDER: tuple[str, ...] = (
    OperatorDecisionSeverity.info.value,
    OperatorDecisionSeverity.low.value,
    OperatorDecisionSeverity.medium.value,
    OperatorDecisionSeverity.high.value,
    OperatorDecisionSeverity.critical.value,
)

_REVIEW_INTERVAL_DAYS: dict[str, int] = {
    "critical": 7,
    "weak": 14,
    "adequate": 30,
    "strong": 90,
}

# Deterministic registry hints (human-facing suggestions only; not eligibility confirmation).
_LANE_HINTS: dict[str, dict[str, list[str]]] = {
    "federal_native_specific": {
        "recommended_source_types": ["federal"],
        "suggested_search_targets": [
            "BIA",
            "IHS",
            "ANA",
            "CTAS",
            "DOE Office of Indian Energy",
            "HUD ONAP",
            "EPA Tribal",
        ],
    },
    "federal_native_relevant_broad": {
        "recommended_source_types": ["federal"],
        "suggested_search_targets": [
            "Grants.gov tribal eligible searches",
            "SAM.gov Assistance Listings",
            "Federal Register NOFOs",
        ],
    },
    "foundation_native_serving": {
        "recommended_source_types": ["foundation", "philanthropic_network"],
        "suggested_search_targets": [
            "Native Americans in Philanthropy",
            "First Nations Development Institute",
            "NDN Collective",
            "Bush Foundation",
        ],
    },
    "corporate_philanthropy": {
        "recommended_source_types": ["corporate"],
        "suggested_search_targets": [
            "corporate foundation Native community grants",
            "broadband philanthropy",
            "energy transition philanthropy",
            "health equity philanthropy",
        ],
    },
    "university_research": {
        "recommended_source_types": ["university"],
        "suggested_search_targets": [
            "tribal college research",
            "Indigenous research institutes",
            "university community partnership grants",
        ],
    },
    "general_broad_with_native_eligibility": {
        "recommended_source_types": ["private", "other"],
        "suggested_search_targets": [
            "rural broadband",
            "health equity",
            "environmental justice",
            "housing",
            "workforce",
            "education programs where Native entities may be eligible",
        ],
    },
    "tribal_government": {
        "recommended_source_types": ["tribal"],
        "suggested_search_targets": [
            "tribal nation portals",
            "tribal compact programs",
        ],
    },
    "tribal_college": {
        "recommended_source_types": ["university", "nonprofit"],
        "suggested_search_targets": ["TCU programs", "tribal college grant offices"],
    },
    "native_nonprofit": {
        "recommended_source_types": ["nonprofit"],
        "suggested_search_targets": ["Native-led nonprofits", "501(c)(3) tribal orgs"],
    },
    "alaska_native": {
        "recommended_source_types": ["nonprofit", "state", "regional"],
        "suggested_search_targets": [
            "Alaska Native corporations",
            "Alaska village priorities",
        ],
    },
    "native_hawaiian": {
        "recommended_source_types": ["nonprofit", "state"],
        "suggested_search_targets": [
            "Native Hawaiian organizations",
            "Hawaiʻi community funds",
        ],
    },
    "state_local_native_relevant": {
        "recommended_source_types": ["state", "local", "regional"],
        "suggested_search_targets": [
            "state broadband offices",
            "regional planning grants",
            "local equity programs",
        ],
    },
}


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _cap_priority(priority: str, *, posture: str) -> str:
    if posture != "strong":
        return priority
    if priority not in _PRIORITY_ORDER:
        return _STRONG_POSTURE_PRIORITY_CAP
    cap_i = _PRIORITY_ORDER.index(_STRONG_POSTURE_PRIORITY_CAP)
    p_i = _PRIORITY_ORDER.index(priority)
    return _PRIORITY_ORDER[min(p_i, cap_i)]


def _lane_priority_base(
    lane: str,
    plan_status: str,
    *,
    posture: str,
) -> str:
    if plan_status == "missing":
        if lane == "federal_native_specific":
            pri = (
                OperatorDecisionSeverity.critical.value
                if posture in {"critical", "weak"}
                else OperatorDecisionSeverity.high.value
            )
        elif lane in _PHILANTHROPY_LANES:
            pri = OperatorDecisionSeverity.high.value
        else:
            pri = OperatorDecisionSeverity.medium.value
    elif plan_status == "weak":
        pri = (
            OperatorDecisionSeverity.high.value
            if lane == "federal_native_specific"
            else OperatorDecisionSeverity.medium.value
        )
    elif plan_status == "overrepresented":
        pri = OperatorDecisionSeverity.low.value
    elif plan_status == "healthy":
        pri = OperatorDecisionSeverity.low.value
    else:
        pri = OperatorDecisionSeverity.medium.value
    return _cap_priority(pri, posture=posture)


def _evidence_refs(sq: dict[str, Any]) -> list[str]:
    refs: list[str] = []
    for row in (sq.get("top_attention_sources") or [])[:5]:
        sid = row.get("source_registry_id")
        if sid:
            refs.append(f"source_registry:{sid}")
    for g in (sq.get("top_coverage_gaps") or [])[:4]:
        gid = g.get("gap_id")
        if gid:
            refs.append(f"coverage_gap:{gid}")
    return refs


def _detail_by_lane(sq: dict[str, Any]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for row in sq.get("priority_lane_coverage") or []:
        ln = row.get("lane")
        if isinstance(ln, str) and ln:
            out[ln] = row
    return out


def _plan_lane_status(
    lane: str,
    *,
    detail: dict[str, Any] | None,
    over: set[str],
    healthy_frac: float,
    cnt: int,
) -> str:
    if cnt <= 0:
        return "missing"
    if lane in over:
        return "overrepresented"
    raw = str((detail or {}).get("status") or "")
    if raw == "weak":
        return "weak"
    if healthy_frac >= 0.75 and cnt >= 2:
        return "healthy"
    return "adequate"


def _target_count(
    lane: str,
    plan_status: str,
    cnt: int,
    active_n: int,
) -> int:
    if plan_status == "missing":
        return 2 if lane == "federal_native_specific" else 1
    if plan_status == "weak":
        return max(2, cnt + 1)
    if plan_status == "overrepresented":
        return cnt
    if plan_status == "healthy":
        return cnt
    return max(cnt, 2) if cnt > 0 else 1


def _health_pressure(sq: dict[str, Any]) -> int:
    hc = sq.get("health_counts") or {}
    keys = ("failing", "empty", "stale", "degraded", "attention_needed")
    return sum(int(hc.get(k, 0) or 0) for k in keys)


def _severe_health(sq: dict[str, Any]) -> bool:
    hc = sq.get("health_counts") or {}
    return int(hc.get("failing", 0) or 0) > 0 or int(hc.get("empty", 0) or 0) > 0


def _risk_flags(sq: dict[str, Any], lane_rows: list[dict[str, Any]]) -> list[str]:
    flags: list[str] = []
    missing = set(sq.get("missing_lanes") or [])
    if "federal_native_specific" in missing:
        flags.append("no_native_specific_sources")
    if "foundation_native_serving" in missing:
        flags.append("no_foundation_sources")
    fc = sq.get("freshness_counts") or {}
    if (
        int(fc.get("overdue_for_check") or 0) >= 2
        or int(fc.get("missing_recent_check") or 0) >= 3
    ):
        flags.append("stale_source_network")
    if sq.get("overrepresented_lanes"):
        flags.append("overconcentrated_lane")
    for row in lane_rows:
        if row.get("lane") == "general_broad_with_native_eligibility" and row.get(
            "status"
        ) in {"weak", "missing"}:
            flags.append("weak_broad_eligibility_lane")
            break
    return sorted(set(flags))


def _lane_rationale(lane: str, plan_status: str) -> str:
    if lane == "general_broad_with_native_eligibility" and plan_status in {
        "weak",
        "missing",
    }:
        return (
            "Broad eligibility monitoring may surface keyword-only Native relevance; human review "
            "is required before treating signals as confirmed eligibility (Native-first, not Native-only)."
        )
    if plan_status == "missing":
        return (
            "Doctrine lane has no active mapped sources; add registry entries using structured "
            "metadata—do not infer eligibility from keywords alone."
        )
    if plan_status == "weak":
        return "Lane is thin or mostly unhealthy among supporters; add parallel sources or remediate health."
    if plan_status == "overrepresented":
        return (
            "Lane dominates the portfolio; diversify by adding underrepresented lanes rather than "
            "shrinking the active portfolio to rebalance."
        )
    if plan_status == "healthy":
        return (
            "Lane shows healthy supporter coverage; maintain cadence and monitor drift."
        )
    return "Lane is adequately represented; continue periodic verification."


def _lane_next_step(plan_status: str, lane: str) -> str:
    if plan_status == "missing":
        return f"Add or activate registry sources mapped to `{lane}`."
    if plan_status == "weak":
        if lane == "general_broad_with_native_eligibility":
            return (
                "Broaden monitoring for general eligibility channels; human review required "
                "before treating keyword-only Native mentions as confirmed eligibility."
            )
        return "Add parallel sources or improve health for lane supporters."
    if plan_status == "overrepresented":
        return (
            "Diversify the active mix by adding underrepresented doctrine lanes; "
            "avoid shrinking the portfolio solely to reduce concentration."
        )
    if plan_status == "healthy":
        return "Maintain cadence and health checks; watch for drift."
    return "Continue periodic verification and gap monitoring."


def _impact(action_type: str) -> str:
    return {
        "expand_native_priority_coverage": "Improves Native priority lane breadth and trust.",
        "target_lane_coverage": "Closes a high-value doctrine lane gap.",
        "diversify_source_mix": "Reduces single-lane dependency without shrinking the portfolio.",
        "maintain_source_health": "Stabilizes ingestion reliability before expansion.",
        "clear_overdue_source_checks": "Restores freshness bookkeeping discipline.",
        "monitor_broad_eligibility": "Keeps broad-eligibility monitoring honest via review.",
        "maintenance_posture": "Preserves strong registry posture with light-touch checks.",
    }.get(
        action_type,
        "Supports registry quality and Native-first coverage doctrine.",
    )


def _sequenced_steps(
    sq: dict[str, Any],
    *,
    posture: str,
    active_n: int,
    missing_lanes: list[str],
    over_lanes: list[str],
) -> list[dict[str, Any]]:
    steps: list[dict[str, Any]] = []
    hc = sq.get("health_counts") or {}
    fc = sq.get("freshness_counts") or {}
    hp = _health_pressure(sq)
    severe = _severe_health(sq)
    phil_missing = [ln for ln in _PHILANTHROPY_LANES if ln in set(missing_lanes)]

    def push(
        *,
        action_type: str,
        priority: str,
        title: str,
        rationale: str,
        focus_lanes: list[str],
        depends_on: list[int],
    ) -> None:
        pri = _cap_priority(priority, posture=posture)
        steps.append(
            _json_safe(
                {
                    "step_number": len(steps) + 1,
                    "action_type": action_type,
                    "priority": pri,
                    "title": title,
                    "rationale": rationale,
                    "focus_lanes": sorted(set(focus_lanes)),
                    "expected_quality_impact": _impact(action_type),
                    "depends_on": list(depends_on),
                    "should_create_action": False,
                }
            )
        )

    if active_n == 0:
        push(
            action_type="expand_native_priority_coverage",
            priority=OperatorDecisionSeverity.critical.value,
            title="Seed minimum viable Native source registry",
            rationale=(
                "No active sources—establish doctrine-aligned federal, tribal, philanthropic, "
                "and broad-eligibility monitoring sources before scaling discovery."
            ),
            focus_lanes=list(missing_lanes)[:12],
            depends_on=[],
        )
        return steps

    health_dep: list[int] = []
    if severe:
        h_pri = (
            OperatorDecisionSeverity.high.value
            if (int(hc.get("failing", 0) or 0) > 0 or int(hc.get("empty", 0) or 0) > 0)
            else OperatorDecisionSeverity.medium.value
        )
        push(
            action_type="maintain_source_health",
            priority=h_pri,
            title="Remediate failing or empty-run sources before expanding coverage",
            rationale=(
                "Severe registry health pressure (failing or repeated empty checks) must be "
                "addressed before adding new lanes so expansion builds on reliable ingestion."
            ),
            focus_lanes=[],
            depends_on=[],
        )
        health_dep = [1]

    if "federal_native_specific" in missing_lanes:
        push(
            action_type="target_lane_coverage",
            priority=OperatorDecisionSeverity.high.value,
            title="Cover federal Native-specific programs lane",
            rationale=(
                "Federal Native-specific doctrine lane is absent; add federal registry sources "
                "with tribally targeted program signals. Native-first priority—confirm eligibility "
                "from publisher rules, not keyword hints alone."
            ),
            focus_lanes=["federal_native_specific"],
            depends_on=health_dep.copy(),
        )

    if phil_missing:
        push(
            action_type="diversify_source_mix",
            priority=OperatorDecisionSeverity.medium.value,
            title="Add foundation and corporate philanthropy lane depth",
            rationale=(
                "Philanthropy doctrine lanes are missing; diversify beyond federal-heavy mixes "
                "with Native-serving foundation and CSR-class registry entries."
            ),
            focus_lanes=list(phil_missing),
            depends_on=health_dep.copy(),
        )

    if over_lanes:
        push(
            action_type="diversify_source_mix",
            priority=OperatorDecisionSeverity.medium.value,
            title="Reduce doctrine lane concentration through diversification",
            rationale=(
                "One or more lanes dominate the active portfolio; add underrepresented doctrine "
                "lanes to rebalance concentration through diversification rather than shrinking "
                "source counts."
            ),
            focus_lanes=list(over_lanes)[:8],
            depends_on=health_dep.copy(),
        )

    broad_detail = (
        _detail_by_lane(sq).get("general_broad_with_native_eligibility") or {}
    )
    if str(broad_detail.get("status") or "") == "weak":
        push(
            action_type="monitor_broad_eligibility",
            priority=OperatorDecisionSeverity.medium.value,
            title="Review broad eligibility lane monitoring",
            rationale=(
                "General broad eligibility lane is thin; broaden structured monitoring. "
                "Human review required—keyword-only Native relevance does not confirm eligibility."
            ),
            focus_lanes=["general_broad_with_native_eligibility"],
            depends_on=health_dep.copy(),
        )

    if not severe and hp > 0:
        push(
            action_type="maintain_source_health",
            priority=(
                OperatorDecisionSeverity.high.value
                if (
                    int(hc.get("failing", 0) or 0) > 0
                    or int(hc.get("empty", 0) or 0) > 0
                )
                else OperatorDecisionSeverity.medium.value
            ),
            title="Remediate stale, degraded, or failing registry sources",
            rationale=(
                "Registry health pressure from failing runs, empty streaks, staleness, or "
                "attention states; verify connectors and checks."
            ),
            focus_lanes=[],
            depends_on=[],
        )

    overdue_n = int(fc.get("overdue_for_check") or 0)
    if overdue_n > 0:
        push(
            action_type="clear_overdue_source_checks",
            priority=OperatorDecisionSeverity.medium.value,
            title="Clear overdue discovery source checks",
            rationale=(
                "Active sources are overdue for scheduled checks; run checks or adjust cadence."
            ),
            focus_lanes=[],
            depends_on=[],
        )

    if len(missing_lanes) >= 5:
        push(
            action_type="expand_native_priority_coverage",
            priority=OperatorDecisionSeverity.high.value,
            title="Expand underrepresented Native priority lanes",
            rationale=(
                "Several doctrine lanes remain uncovered; prioritize registry expansion mapped to "
                "Native priority lanes—preserve Native-first, not Native-only coverage."
            ),
            focus_lanes=missing_lanes[:8],
            depends_on=health_dep.copy(),
        )
    elif missing_lanes and len(missing_lanes) < 5:
        residual = len(missing_lanes) > 1 or (
            len(missing_lanes) == 1 and missing_lanes[0] != "federal_native_specific"
        )
        if residual and not any(
            s.get("action_type") == "expand_native_priority_coverage" for s in steps
        ):
            push(
                action_type="expand_native_priority_coverage",
                priority=OperatorDecisionSeverity.medium.value,
                title="Fill remaining Native priority lane gaps",
                rationale=(
                    "Add or activate sources that map to missing doctrine lanes to complete "
                    "Native-relevant coverage."
                ),
                focus_lanes=missing_lanes[:8],
                depends_on=health_dep.copy(),
            )

    if posture == "strong" and not steps:
        push(
            action_type="maintenance_posture",
            priority=OperatorDecisionSeverity.low.value,
            title="Maintain registry posture and harden residual gaps",
            rationale=(
                "Registry posture is strong; focus on periodic verification, residual lane gaps, "
                "and drift monitoring rather than urgent expansion."
            ),
            focus_lanes=[],
            depends_on=[],
        )

    # Strong posture: drop urgent expansion language by removing high/critical expansion steps.
    if posture == "strong":
        filtered: list[dict[str, Any]] = []
        for st in steps:
            at = str(st.get("action_type") or "")
            pr = str(st.get("priority") or "")
            if at in {
                "expand_native_priority_coverage",
                "target_lane_coverage",
            } and pr in {"high", "critical"}:
                st = dict(st)
                st["priority"] = _STRONG_POSTURE_PRIORITY_CAP
                st["rationale"] = (
                    str(st.get("rationale") or "")
                    + " (Strong posture: treat as maintenance-scale lane gap, not urgent expansion.)"
                )
            filtered.append(st)
        steps = filtered

    # Re-number steps after potential edits (strong filter didn't remove steps).
    for i, st in enumerate(steps):
        st["step_number"] = i + 1

    return [_json_safe(s) for s in steps]


def _summary(
    sq: dict[str, Any],
    *,
    posture: str,
    missing_lanes: list[str],
    risk_flags: list[str],
) -> str:
    org = str(sq.get("organization_id") or "")
    if posture == "critical":
        return (
            f"Organization {org}: registry is empty—seed a minimum viable Native-aligned source "
            "network before relying on discovery outputs."
        )
    if posture == "strong":
        return (
            f"Organization {org}: source coverage posture is strong; execute maintenance, "
            "residual gap checks, and diversification only where lanes drift."
        )
    parts = [
        f"Organization {org}: improve Native-first coverage",
        f"({len(missing_lanes)} missing doctrine lanes)",
    ]
    if risk_flags:
        parts.append(f"flags: {', '.join(risk_flags)}")
    return " ".join(parts) + "."


def build_source_coverage_plan(source_quality: dict[str, Any]) -> dict[str, Any]:
    """Return nf_source_coverage_plan_v1 from a nf_discovery_source_quality_v1 dict."""
    sq = dict(source_quality)
    posture = str(sq.get("posture") or "adequate")
    dqs = int(sq.get("data_quality_score") or 0)
    sc = sq.get("source_counts") or {}
    active_n = int(sc.get("active") or 0)
    org_id = str(sq.get("organization_id") or "")
    gen_at = sq.get("generated_at") or ""

    over_list = list(sq.get("overrepresented_lanes") or [])
    over_set = set(over_list)
    missing_lanes = list(sq.get("missing_lanes") or [])

    detail_map = _detail_by_lane(sq)
    evidence = _evidence_refs(sq)

    priority_lanes: list[dict[str, Any]] = []
    for lane in _PLAN_LANES:
        detail = detail_map.get(lane)
        cnt = int((detail or {}).get("active_source_count") or 0)
        hf = float((detail or {}).get("healthy_fraction") or 0.0)
        plan_status = _plan_lane_status(
            lane,
            detail=detail,
            over=over_set,
            healthy_frac=hf,
            cnt=cnt,
        )
        lane_pri = _lane_priority_base(lane, plan_status, posture=posture)
        hints = _LANE_HINTS.get(
            lane,
            {"recommended_source_types": [], "suggested_search_targets": []},
        )
        priority_lanes.append(
            _json_safe(
                {
                    "lane": lane,
                    "status": plan_status,
                    "priority": lane_pri,
                    "rationale": _lane_rationale(lane, plan_status),
                    "current_source_count": cnt,
                    "target_source_count": _target_count(
                        lane, plan_status, cnt, active_n
                    ),
                    "recommended_source_types": list(
                        hints.get("recommended_source_types") or []
                    ),
                    "suggested_search_targets": list(
                        hints.get("suggested_search_targets") or []
                    ),
                    "next_operator_step": _lane_next_step(plan_status, lane),
                    "evidence_refs": list(evidence),
                }
            )
        )

    risk = _risk_flags(sq, priority_lanes)
    seq = _sequenced_steps(
        sq,
        posture=posture,
        active_n=active_n,
        missing_lanes=missing_lanes,
        over_lanes=over_list,
    )

    review_days = int(_REVIEW_INTERVAL_DAYS.get(posture, 30))

    out: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "organization_scope": {
            "organization_id": org_id,
            "generated_at": gen_at,
        },
        "coverage_posture": {
            "posture": posture,
            "data_quality_score": dqs,
            "active_source_count": active_n,
        },
        "priority_lanes": priority_lanes,
        "sequenced_plan": seq,
        "risk_flags": risk,
        "summary": _summary(
            sq, posture=posture, missing_lanes=missing_lanes, risk_flags=risk
        ),
        "recommended_review_interval_days": review_days,
    }
    return _json_safe(out)
