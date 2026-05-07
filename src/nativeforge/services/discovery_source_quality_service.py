"""Sprint 33: deterministic discovery source quality / coverage summary (offline)."""

from __future__ import annotations

import json
import uuid
from collections import Counter
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import Session

from nativeforge.db.models import NfOpportunitySource
from nativeforge.domain.enums import (
    OpportunitySourceType,
    SourceHealthStatus,
    SourcePriorityLevel,
)
from nativeforge.lib.demo_isolation import OrgType
from nativeforge.services import discovery_coverage_gap_service as dcg_svc
from nativeforge.services import opportunity_discovery_service as ods
from nativeforge.services import source_freshness_service as sfs
from nativeforge.services.discovery_coverage_gap_ids import (
    severity_rank as _gap_severity_rank,
)

SCHEMA_VERSION = "nf_discovery_source_quality_v1"

# Doctrine-aligned priority lanes (deterministic mapping from registry metadata).
NATIVE_PRIORITY_LANES: tuple[str, ...] = (
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

_PRIORITY_WEIGHT: dict[str, int] = {
    SourcePriorityLevel.critical.value: 5,
    SourcePriorityLevel.high.value: 4,
    SourcePriorityLevel.medium.value: 3,
    SourcePriorityLevel.low.value: 2,
}

_BAD_HEALTH: frozenset[str] = frozenset(
    {
        SourceHealthStatus.stale.value,
        SourceHealthStatus.degraded.value,
        SourceHealthStatus.failing.value,
        SourceHealthStatus.attention_needed.value,
    }
)


def _json_safe(x: Any) -> Any:
    """Ensure JSON-serializable plain types only."""
    json.dumps(x)
    return x


def _applicant_tokens(source: NfOpportunitySource) -> set[str]:
    raw = source.applicant_types_json
    out: set[str] = set()
    if isinstance(raw, list):
        for x in raw:
            out.add(str(x).strip().lower())
    elif isinstance(raw, dict):
        for k in raw.keys():
            out.add(str(k).strip().lower())
    return out


def _domain_tokens(source: NfOpportunitySource) -> set[str]:
    fds = source.funding_domains_json
    if not isinstance(fds, list):
        return set()
    return {str(d).strip().lower() for d in fds}


def _state_codes_upper(source: NfOpportunitySource) -> set[str]:
    cs = source.covered_states_json
    if not isinstance(cs, list):
        return set()
    return {str(x).strip().upper()[:8] for x in cs if str(x).strip()}


def _region_keys(source: NfOpportunitySource) -> set[str]:
    cr = source.covered_regions_json
    if not isinstance(cr, list):
        return set()
    return {str(x).strip().lower() for x in cr if str(x).strip()}


def _tribal_group_keys(source: NfOpportunitySource) -> set[str]:
    tg = source.covered_tribal_groups_json
    if not isinstance(tg, list):
        return set()
    return {str(x).strip().lower() for x in tg if str(x).strip()}


def _text_blob(source: NfOpportunitySource) -> str:
    parts = [
        source.source_name or "",
        source.description or "",
        source.native_relevance_notes or "",
        source.publisher_name or "",
    ]
    return " ".join(parts).lower()


def priority_lanes_for_source(source: NfOpportunitySource) -> frozenset[str]:
    """Map one registry row to zero or more doctrine priority lanes (deterministic)."""
    if not source.is_active:
        return frozenset()
    st = str(source.source_type or "").strip().lower()
    apps = _applicant_tokens(source)
    domains = _domain_tokens(source)
    states = _state_codes_upper(source)
    regions = _region_keys(source)
    tribal_g = _tribal_group_keys(source)
    blob = _text_blob(source)

    lanes: set[str] = set()

    fed_specific_signals = (
        "language_culture" in domains
        or "ihbg" in blob
        or "tribal_eligible" in domains
        or "tribal_government" in apps
        or "federally_recognized_tribe" in apps
        or "tribal_college" in apps
        or "bia" in blob
        or "bureau of indian" in blob
        or "indian affairs" in blob
        or "ihs" in blob
        or "native affairs" in blob
    )
    if st == OpportunitySourceType.federal.value:
        lanes.add("federal_native_relevant_broad")
        if fed_specific_signals:
            lanes.add("federal_native_specific")

    if (
        st == OpportunitySourceType.tribal.value
        or "tribal_government" in apps
        or "federally_recognized_tribe" in apps
        or "tribal_organization" in apps
    ):
        lanes.add("tribal_government")

    if (
        "tribal_college" in apps
        or "tribal_college" in domains
        or "tribal_colleges" in tribal_g
        or "tribal college" in blob
        or "tcu" in blob
    ):
        lanes.add("tribal_college")

    if (
        st == OpportunitySourceType.nonprofit.value
        or "tribal_nonprofit" in apps
        or "native_serving_nonprofit" in apps
    ):
        lanes.add("native_nonprofit")

    if (
        "AK" in states
        or "alaska" in regions
        or "alaska_native" in domains
        or "alaska_native_corporation" in apps
        or "alaska_native_village" in apps
        or "alaska" in tribal_g
        or "alaska native" in blob
    ):
        lanes.add("alaska_native")

    if (
        "HI" in states
        or "native_hawaiian_organization" in apps
        or "native_hawaiian" in domains
        or "hawaiian" in tribal_g
        or "native hawaiian" in blob
        or "hawaii" in blob
    ):
        lanes.add("native_hawaiian")

    if st in {
        OpportunitySourceType.state.value,
        OpportunitySourceType.local.value,
        OpportunitySourceType.regional.value,
    }:
        lanes.add("state_local_native_relevant")

    if st in {
        OpportunitySourceType.foundation.value,
        OpportunitySourceType.philanthropic_network.value,
    } or ("foundation" in blob and st != OpportunitySourceType.corporate.value):
        lanes.add("foundation_native_serving")

    if st == OpportunitySourceType.corporate.value or "csr" in blob:
        lanes.add("corporate_philanthropy")

    if st == OpportunitySourceType.university.value:
        lanes.add("university_research")

    if (
        st
        in {
            OpportunitySourceType.private.value,
            OpportunitySourceType.other.value,
        }
        or source.native_relevance_notes
        or "native" in blob
        or "tribal" in blob
        or "indigenous" in blob
        or domains.intersection(
            {"language_culture", "climate_resilience", "education", "health"}
        )
    ):
        lanes.add("general_broad_with_native_eligibility")

    return frozenset(lanes)


def _exclusive_health_bucket(source: NfOpportunitySource) -> str | None:
    if not source.is_active:
        return None
    if (
        source.source_health_status == SourceHealthStatus.failing.value
        or int(source.consecutive_failure_count or 0) >= 3
    ):
        return "failing"
    if int(source.consecutive_empty_check_count or 0) >= 3:
        return "empty"
    raw_h = str(source.source_health_status or "").strip()
    h = raw_h or SourceHealthStatus.unknown.value
    return h


def _attention_rank_score(source: NfOpportunitySource, *, now: datetime) -> int:
    """Higher = needs attention sooner."""
    bucket = _exclusive_health_bucket(source) or "unknown"
    base = {
        "failing": 100,
        "degraded": 85,
        "stale": 78,
        "empty": 72,
        "attention_needed": 68,
        "unknown": 45,
        "healthy": 10,
    }.get(bucket, 40)
    pl = source.priority_level or SourcePriorityLevel.medium.value
    boost = 4 * _PRIORITY_WEIGHT.get(pl, 2)
    overdue = sfs.is_active_source_overdue(source, now=now)
    never = source.last_checked_at is None
    sched = 22 if overdue else 0
    sched += 12 if never else 0
    return base + boost + sched


def _lane_strength(
    sources: list[NfOpportunitySource],
    *,
    lane: str,
    lane_membership: dict[uuid.UUID, frozenset[str]],
) -> tuple[int, float]:
    """Return (supporting_active_count, healthy_fraction among supporters)."""
    supporters = [
        s
        for s in sources
        if s.is_active and lane in lane_membership.get(s.id, frozenset())
    ]
    if not supporters:
        return 0, 0.0
    good = sum(
        1
        for s in supporters
        if (s.source_health_status or "") == SourceHealthStatus.healthy.value
    )
    return len(supporters), good / len(supporters)


def build_discovery_source_quality(
    session: Session,
    *,
    org_id: uuid.UUID,
    org_type: OrgType,
    now: datetime | None = None,
    top_attention_limit: int = 24,
    top_gap_limit: int = 16,
) -> dict[str, Any]:
    """Deterministic org-scoped source quality + Native priority lane coverage."""
    ref_now = now or datetime.now(UTC)
    rows = ods.list_sources(session, org_id=org_id, org_type=org_type)
    active_rows = [r for r in rows if r.is_active]
    gap_intel = dcg_svc.build_coverage_gap_intelligence(
        session,
        org_id=org_id,
        org_type=org_type,
        now=ref_now,
    )
    cov_summary = ods.discovery_coverage_summary(rows)

    lane_by_source: dict[uuid.UUID, frozenset[str]] = {
        r.id: priority_lanes_for_source(r) for r in active_rows
    }
    lane_counts: Counter[str] = Counter()
    for lanes in lane_by_source.values():
        for ln in lanes:
            lane_counts[ln] += 1

    covered_lanes = {ln for ln, n in lane_counts.items() if n > 0}
    missing_lanes = [ln for ln in NATIVE_PRIORITY_LANES if ln not in covered_lanes]

    weak_lanes: list[str] = []
    overrepresented_lanes: list[str] = []
    lane_detail: list[dict[str, Any]] = []
    active_n = len(active_rows)
    for ln in NATIVE_PRIORITY_LANES:
        cnt, healthy_frac = _lane_strength(
            active_rows,
            lane=ln,
            lane_membership=lane_by_source,
        )
        status = "missing"
        if cnt > 0:
            status = "weak" if healthy_frac < 0.5 or cnt == 1 else "covered"
        if status == "weak":
            weak_lanes.append(ln)
        lane_detail.append(
            {
                "lane": ln,
                "active_source_count": cnt,
                "healthy_fraction": round(healthy_frac, 4),
                "status": status,
            }
        )
        if active_n >= 4 and cnt >= 3:
            share = cnt / active_n
            if share >= 0.55:
                overrepresented_lanes.append(ln)

    overrepresented_lanes = sorted(set(overrepresented_lanes))

    # Structural source-type categories (OpportunitySourceType universe).
    represented_types = {k for k, v in cov_summary["by_source_type"].items() if v > 0}
    universe = [e.value for e in OpportunitySourceType]
    missing_types = [t for t in universe if t not in represented_types]
    category_coverage: list[dict[str, Any]] = []
    by_st = cov_summary["by_source_type"]
    mean_share = 1.0 / max(len(universe), 1)
    for t in universe:
        n = int(by_st.get(t, 0))
        if n == 0:
            cat_status = "missing"
        elif active_n > 0 and (n / active_n) > max(0.45, 3 * mean_share):
            cat_status = "overrepresented"
        elif n == 1 and active_n > 2:
            cat_status = "weak"
        else:
            cat_status = "covered"
        category_coverage.append(
            {
                "source_type": t,
                "registry_row_count": n,
                "status": cat_status,
            }
        )

    health_counts: dict[str, int] = {
        "healthy": 0,
        "stale": 0,
        "failing": 0,
        "degraded": 0,
        "empty": 0,
        "attention_needed": 0,
        "unknown": 0,
    }
    for r in active_rows:
        b = _exclusive_health_bucket(r)
        if b is None:
            continue
        if b == "empty":
            health_counts["empty"] += 1
            continue
        if b in health_counts:
            health_counts[b] += 1
        else:
            health_counts["unknown"] += 1

    freshness_counts = {
        "never_checked": sum(1 for r in active_rows if r.last_checked_at is None),
        "overdue_for_check": sum(
            1 for r in active_rows if sfs.is_active_source_overdue(r, now=ref_now)
        ),
        "missing_recent_check": sum(
            1
            for r in active_rows
            if r.last_checked_at is None or sfs.is_active_source_overdue(r, now=ref_now)
        ),
        "due_but_not_overdue": sum(
            1
            for r in active_rows
            if r.last_checked_at is not None
            and sfs.is_active_source_due(r, now=ref_now)
            and not sfs.is_active_source_overdue(r, now=ref_now)
        ),
    }

    top_attention_sources = sorted(
        active_rows,
        key=lambda r: (-_attention_rank_score(r, now=ref_now), r.source_name.lower()),
    )[: max(1, min(int(top_attention_limit), 48))]
    attention_payload = [
        {
            "rank": i + 1,
            "source_registry_id": str(r.id),
            "source_name": r.source_name,
            "attention_score": _attention_rank_score(r, now=ref_now),
            "health_bucket": _exclusive_health_bucket(r),
            "priority_level": r.priority_level,
            "source_health_status": r.source_health_status,
            "last_checked_at": r.last_checked_at.isoformat()
            if r.last_checked_at
            else None,
            "is_overdue_for_check": sfs.is_active_source_overdue(r, now=ref_now),
        }
        for i, r in enumerate(top_attention_sources)
    ]

    gaps_sorted = sorted(
        gap_intel.get("coverage_gaps") or [],
        key=lambda g: (
            -_gap_severity_rank(str(g.get("severity") or "")),
            str(g.get("title") or ""),
        ),
    )[: max(1, min(int(top_gap_limit), 48))]
    top_coverage_gaps = [
        {
            "gap_id": str(g.get("gap_id")),
            "gap_type": g.get("gap_type"),
            "severity": g.get("severity"),
            "title": g.get("title"),
        }
        for g in gaps_sorted
    ]

    cov_s = int(gap_intel.get("coverage_score") or 0)
    fresh_s = int(gap_intel.get("freshness_score") or 0)
    rel_s = int(gap_intel.get("reliability_score") or 0)
    yield_s = int(gap_intel.get("yield_score") or 0)
    burden_s = int(gap_intel.get("review_burden_score") or 0)
    base = (cov_s + fresh_s + rel_s + yield_s) / 4.0
    burden_penalty = min(28.0, burden_s * 0.22)
    missing_lane_penalty = min(42.0, len(missing_lanes) * 4.0)
    weak_lane_penalty = min(18.0, len(weak_lanes) * 3.0)
    raw_score = base - burden_penalty - missing_lane_penalty - weak_lane_penalty
    data_quality_score = int(max(0, min(100, round(raw_score))))

    reason_codes: list[str] = []
    if active_n == 0:
        reason_codes.append("no_active_sources")
    if missing_lanes:
        reason_codes.append(f"missing_priority_lanes:{len(missing_lanes)}")
    if health_counts["failing"]:
        reason_codes.append(f"failing_sources:{health_counts['failing']}")
    if freshness_counts["missing_recent_check"]:
        reason_codes.append(
            f"missing_recent_checks:{freshness_counts['missing_recent_check']}"
        )
    if cov_s < 55:
        reason_codes.append("low_coverage_score")
    if fresh_s < 55:
        reason_codes.append("low_freshness_score")

    if active_n == 0:
        posture = "critical"
    elif data_quality_score < 38 or len(missing_lanes) >= 10:
        posture = "weak"
    elif data_quality_score < 68 or len(missing_lanes) >= 5:
        posture = "adequate"
    else:
        posture = "strong"

    recommended_operator_actions: list[dict[str, Any]] = []
    if missing_lanes[:5]:
        recommended_operator_actions.append(
            {
                "action": "expand_registry",
                "focus_lanes": missing_lanes[:5],
                "rationale": (
                    "Add or activate sources mapped to missing Native priority lanes."
                ),
            }
        )
    if health_counts["failing"] or health_counts["empty"]:
        recommended_operator_actions.append(
            {
                "action": "remediate_source_health",
                "rationale": (
                    "Investigate failing sources and repeated empty check streaks."
                ),
            }
        )
    if freshness_counts["overdue_for_check"]:
        recommended_operator_actions.append(
            {
                "action": "run_overdue_source_checks",
                "count": freshness_counts["overdue_for_check"],
                "rationale": (
                    "Clear overdue discovery source checks to refresh bookkeeping."
                ),
            }
        )

    is_demo = org_type == "demo"
    out: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "organization_id": str(org_id),
        "is_demo": is_demo,
        "generated_at": ref_now.isoformat(),
        "source_counts": {
            "registry_total": len(rows),
            "active": active_n,
            "inactive": len(rows) - active_n,
            "by_source_type_active": {
                k: v for k, v in Counter(r.source_type for r in active_rows).items()
            },
        },
        "health_counts": health_counts,
        "freshness_counts": freshness_counts,
        "category_coverage": category_coverage,
        "missing_source_types": missing_types,
        "priority_lane_coverage": lane_detail,
        "priority_lane_counts": dict(sorted(lane_counts.items())),
        "weak_lanes": sorted(weak_lanes),
        "missing_lanes": missing_lanes,
        "overrepresented_lanes": overrepresented_lanes,
        "top_attention_sources": attention_payload,
        "top_coverage_gaps": top_coverage_gaps,
        "data_quality_score": data_quality_score,
        "posture": posture,
        "reason_codes": reason_codes,
        "recommended_operator_actions": recommended_operator_actions,
        "scores_from_coverage_intel": {
            "coverage_score": cov_s,
            "freshness_score": fresh_s,
            "reliability_score": rel_s,
            "yield_score": yield_s,
            "review_burden_score": burden_s,
        },
        "organization_scope": {"org_id": str(org_id), "plane": org_type},
    }
    return _json_safe(out)


def source_quality_compact(summary: dict[str, Any]) -> dict[str, Any]:
    """Small embedding shape for exports."""
    return {
        "schema_version": summary.get("schema_version"),
        "generated_at": summary.get("generated_at"),
        "data_quality_score": summary.get("data_quality_score"),
        "posture": summary.get("posture"),
        "missing_lane_count": len(summary.get("missing_lanes") or []),
        "active_source_count": (summary.get("source_counts") or {}).get("active"),
    }
