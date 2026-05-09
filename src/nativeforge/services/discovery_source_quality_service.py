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
    OperatorDecisionSeverity,
    OpportunitySourceType,
    SourceHealthStatus,
    SourcePriorityLevel,
)
from nativeforge.lib.demo_isolation import OrgType
from nativeforge.services import (
    active_source_migration_dry_run_plan_service as asmdrp_svc,
)
from nativeforge.services import (
    active_source_migration_file_review_service as asmdfr_svc,
)
from nativeforge.services import (
    active_source_schema_rollback_contract_service as assrc_svc,
)
from nativeforge.services import (
    active_source_local_migration_verification_service as aslmv_svc,
)
from nativeforge.services import (
    active_source_runtime_migration_apply_plan_service as asrmap_svc,
)
from nativeforge.services import (
    active_source_runtime_migration_approval_intake_service as asrmais_svc,
)
from nativeforge.services import (
    active_source_runtime_migration_apply_execution_service as asrmrae_svc,
)
from nativeforge.services import (
    active_source_runtime_migration_dry_run_command_package_service as asrmdrcp_svc,
)
from nativeforge.services import (
    active_source_creation_request_service as ascrcreq_svc,
)
from nativeforge.services import (
    active_source_empty_state_read_model_service as asesrm_svc,
)
from nativeforge.services import (
    active_source_runtime_migration_post_apply_verification_service as asrmrpav_svc,
)
from nativeforge.services import (
    active_source_runtime_migration_readiness_gate_service as asrmrg_svc,
)
from nativeforge.services import (
    alembic_migration_generation_gate_service as amgg_svc,
)
from nativeforge.services import discovery_coverage_gap_service as dcg_svc
from nativeforge.services import opportunity_discovery_service as ods
from nativeforge.services import (
    source_activation_command_dry_run_service as sacdr_svc,
)
from nativeforge.services import (
    source_activation_preview_service as sap_svc,
)
from nativeforge.services import (
    source_activation_readiness_contract_service as sarc_svc,
)
from nativeforge.services import source_candidate_registry_service as scr_svc
from nativeforge.services import source_coverage_plan_service as scp_svc
from nativeforge.services import source_freshness_service as sfs
from nativeforge.services import (
    source_human_approval_artifact_service as sha_svc,
)
from nativeforge.services import source_onboarding_decision_pack_service as sodp_svc
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

# Philanthropy / CSR doctrine lanes (paired diversification signals).
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


def _cap_priority_for_strong_posture(priority: str, *, posture: str) -> str:
    """Strong posture must not surface urgent (high/critical) recommendations."""
    if posture != "strong":
        return priority
    if priority not in _PRIORITY_ORDER:
        return _STRONG_POSTURE_PRIORITY_CAP
    cap_i = _PRIORITY_ORDER.index(_STRONG_POSTURE_PRIORITY_CAP)
    p_i = _PRIORITY_ORDER.index(priority)
    return _PRIORITY_ORDER[min(p_i, cap_i)]


def _health_pressure_count(health_counts: dict[str, int]) -> int:
    keys = (
        "failing",
        "empty",
        "stale",
        "degraded",
        "attention_needed",
    )
    return sum(int(health_counts.get(k, 0)) for k in keys)


def _evidence_refs_for_actions(
    attention: list[dict[str, Any]],
    gaps: list[dict[str, Any]],
    *,
    max_sources: int = 5,
    max_gaps: int = 4,
) -> list[str]:
    refs: list[str] = []
    for row in attention[:max_sources]:
        sid = row.get("source_registry_id")
        if sid:
            refs.append(f"source_registry:{sid}")
    for g in gaps[:max_gaps]:
        gid = g.get("gap_id")
        if gid:
            refs.append(f"coverage_gap:{gid}")
    return refs


def _make_operator_action(
    *,
    action_type: str,
    priority: str,
    title: str,
    rationale: str,
    focus_lanes: list[str],
    affected_source_count: int,
    evidence_refs: list[str],
    posture: str,
    should_create_action: bool = False,
) -> dict[str, Any]:
    pri = _cap_priority_for_strong_posture(priority, posture=posture)
    row: dict[str, Any] = {
        "action_type": action_type,
        "priority": pri,
        "title": title,
        "rationale": rationale,
        "focus_lanes": sorted(set(focus_lanes)),
        "affected_source_count": int(max(0, affected_source_count)),
        "evidence_refs": evidence_refs,
        "should_create_action": bool(should_create_action),
    }
    if evidence_refs:
        row["context_ids"] = list(evidence_refs)
    return row


def _build_recommended_operator_actions(
    *,
    posture: str,
    active_n: int,
    missing_lanes: list[str],
    overrepresented_lanes: list[str],
    health_counts: dict[str, int],
    freshness_counts: dict[str, int],
    top_attention_sources: list[dict[str, Any]],
    top_coverage_gaps: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Build deterministic JSON-serializable recommended operator actions."""
    evidence = _evidence_refs_for_actions(top_attention_sources, top_coverage_gaps)
    actions: list[dict[str, Any]] = []

    if active_n == 0:
        actions.append(
            _make_operator_action(
                action_type="expand_native_priority_coverage",
                priority=OperatorDecisionSeverity.critical.value,
                title="Establish Native priority lane registry coverage",
                rationale=(
                    "No active registry sources; activate or add sources mapped to "
                    "doctrine Native priority lanes before discovery can be "
                    "trustworthy."
                ),
                focus_lanes=list(missing_lanes),
                affected_source_count=0,
                evidence_refs=[r for r in evidence if r.startswith("coverage_gap:")],
                posture=posture,
            )
        )
        return [_json_safe(a) for a in actions]

    phil_missing = [ln for ln in _PHILANTHROPY_LANES if ln in set(missing_lanes)]
    if phil_missing:
        actions.append(
            _make_operator_action(
                action_type="diversify_source_mix",
                priority=OperatorDecisionSeverity.medium.value,
                title="Add foundation and corporate philanthropy lane depth",
                rationale=(
                    "Philanthropy doctrine lanes are missing; add foundation / "
                    "CSR-class sources to balance federal-heavy portfolios."
                ),
                focus_lanes=phil_missing,
                affected_source_count=active_n,
                evidence_refs=evidence,
                posture=posture,
            )
        )

    if "federal_native_specific" in missing_lanes:
        actions.append(
            _make_operator_action(
                action_type="target_lane_coverage",
                priority=OperatorDecisionSeverity.high.value,
                title="Cover federal Native-specific programs lane",
                rationale=(
                    "Federal Native-specific doctrine lane is absent; add federal "
                    "sources with tribally targeted program signals "
                    "(language/culture, BIA/IHS, tribal eligibility domains)."
                ),
                focus_lanes=["federal_native_specific"],
                affected_source_count=active_n,
                evidence_refs=evidence,
                posture=posture,
            )
        )

    if overrepresented_lanes:
        actions.append(
            _make_operator_action(
                action_type="diversify_source_mix",
                priority=OperatorDecisionSeverity.medium.value,
                title="Reduce doctrine lane concentration risk",
                rationale=(
                    "One or more Native priority lanes dominate the active portfolio; "
                    "add sources in underrepresented lanes to reduce single-lane "
                    "dependency."
                ),
                focus_lanes=list(overrepresented_lanes),
                affected_source_count=active_n,
                evidence_refs=evidence,
                posture=posture,
            )
        )

    hp = _health_pressure_count(health_counts)
    if hp > 0:
        actions.append(
            _make_operator_action(
                action_type="maintain_source_health",
                priority=(
                    OperatorDecisionSeverity.high.value
                    if (
                        health_counts.get("failing", 0) > 0
                        or health_counts.get("empty", 0) > 0
                    )
                    else OperatorDecisionSeverity.medium.value
                ),
                title="Remediate stale, degraded, or failing registry sources",
                rationale=(
                    "Registry health pressure from failing runs, empty streaks, "
                    "staleness, or degraded/attention states; verify connectors "
                    "and checks."
                ),
                focus_lanes=[],
                affected_source_count=hp,
                evidence_refs=evidence,
                posture=posture,
            )
        )

    overdue_n = int(freshness_counts.get("overdue_for_check") or 0)
    if overdue_n > 0:
        actions.append(
            _make_operator_action(
                action_type="clear_overdue_source_checks",
                priority=OperatorDecisionSeverity.medium.value,
                title="Clear overdue discovery source checks",
                rationale=(
                    "Active sources are overdue for scheduled checks; run checks or "
                    "adjust cadence so freshness bookkeeping stays current."
                ),
                focus_lanes=[],
                affected_source_count=overdue_n,
                evidence_refs=evidence,
                posture=posture,
            )
        )

    # Broad lane gaps — philanthropy diversification is separate from lane enumeration.
    if len(missing_lanes) >= 5:
        actions.append(
            _make_operator_action(
                action_type="expand_native_priority_coverage",
                priority=OperatorDecisionSeverity.high.value,
                title="Expand underrepresented Native priority lanes",
                rationale=(
                    "Several doctrine lanes remain uncovered; prioritize registry "
                    "expansion mapped to the listed Native priority lanes."
                ),
                focus_lanes=missing_lanes[:8],
                affected_source_count=active_n,
                evidence_refs=evidence,
                posture=posture,
            )
        )
    elif missing_lanes and len(missing_lanes) < 5:
        needs_residual_expand = len(missing_lanes) > 1 or (
            len(missing_lanes) == 1 and missing_lanes[0] != "federal_native_specific"
        )
        if needs_residual_expand and not any(
            a.get("action_type") == "expand_native_priority_coverage" for a in actions
        ):
            actions.append(
                _make_operator_action(
                    action_type="expand_native_priority_coverage",
                    priority=OperatorDecisionSeverity.medium.value,
                    title="Fill remaining Native priority lane gaps",
                    rationale=(
                        "Add or activate sources that map to missing doctrine lanes to "
                        "complete Native-relevant coverage."
                    ),
                    focus_lanes=missing_lanes[:8],
                    affected_source_count=active_n,
                    evidence_refs=evidence,
                    posture=posture,
                )
            )

    # De-duplicate identical action_types with identical focus lanes (deterministic).
    seen: set[tuple[str, tuple[str, ...]]] = set()
    deduped: list[dict[str, Any]] = []
    for a in actions:
        key = (
            str(a.get("action_type") or ""),
            tuple(str(x) for x in (a.get("focus_lanes") or [])),
        )
        if key in seen:
            continue
        seen.add(key)
        deduped.append(a)

    return [_json_safe(x) for x in deduped]


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

    score_breakdown = _json_safe(
        {
            "intel_components": {
                "coverage_score": cov_s,
                "freshness_score": fresh_s,
                "reliability_score": rel_s,
                "yield_score": yield_s,
                "review_burden_score": burden_s,
            },
            "base_average_of_intel": round(base, 4),
            "penalties": {
                "review_burden": round(burden_penalty, 4),
                "missing_priority_lanes": round(missing_lane_penalty, 4),
                "weak_priority_lanes": round(weak_lane_penalty, 4),
            },
            "computed_before_clip": round(raw_score, 4),
            "final_data_quality_score": data_quality_score,
        }
    )

    reason_codes: list[str] = []
    reason_codes.append(f"score_base_intel_average:{round(base, 4)}")
    reason_codes.append(f"penalty_review_burden:{round(burden_penalty, 4)}")
    reason_codes.append(
        f"penalty_missing_priority_lanes:{len(missing_lanes)}:"
        f"{round(missing_lane_penalty, 4)}",
    )
    reason_codes.append(
        f"penalty_weak_priority_lanes:{len(weak_lanes)}:{round(weak_lane_penalty, 4)}",
    )
    reason_codes.append(f"final_data_quality_score:{data_quality_score}")

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
    elif data_quality_score < 62 or len(missing_lanes) >= 5:
        posture = "adequate"
    else:
        posture = "strong"

    recommended_operator_actions = _build_recommended_operator_actions(
        posture=posture,
        active_n=active_n,
        missing_lanes=missing_lanes,
        overrepresented_lanes=overrepresented_lanes,
        health_counts=health_counts,
        freshness_counts=freshness_counts,
        top_attention_sources=attention_payload,
        top_coverage_gaps=top_coverage_gaps,
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
        "score_breakdown": score_breakdown,
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
    out = _json_safe(out)
    out["source_coverage_plan"] = scp_svc.build_source_coverage_plan(out)
    out["source_candidate_registry"] = scr_svc.build_source_candidate_registry(out)
    out["source_onboarding_decision_pack"] = (
        sodp_svc.build_source_onboarding_decision_pack(out)
    )
    out["source_activation_readiness_contract"] = (
        sarc_svc.build_source_activation_readiness_contract(out)
    )
    out["source_activation_preview"] = sap_svc.build_source_activation_preview(out)
    out["source_human_approval_artifact"] = (
        sha_svc.build_source_human_approval_artifact(out)
    )
    out["source_activation_command_dry_run"] = (
        sacdr_svc.build_source_activation_command_dry_run(out)
    )
    out["active_source_schema_rollback_contract"] = (
        assrc_svc.build_active_source_schema_rollback_contract(out)
    )
    out["active_source_migration_dry_run_plan"] = (
        asmdrp_svc.build_active_source_migration_dry_run_plan(out)
    )
    out["alembic_migration_generation_gate"] = (
        amgg_svc.build_alembic_migration_generation_gate(out)
    )
    out["active_source_migration_file_review"] = (
        asmdfr_svc.build_active_source_migration_file_review(out)
    )
    out["active_source_local_migration_verification"] = (
        aslmv_svc.build_active_source_local_migration_verification(out)
    )
    out["active_source_runtime_migration_apply_plan"] = (
        asrmap_svc.build_active_source_runtime_migration_apply_plan(
            out,
            repo_root=asmdfr_svc._repo_root(),
        )
    )
    out["active_source_runtime_migration_approval_intake"] = (
        asrmais_svc.build_active_source_runtime_migration_approval_intake(None)
    )
    out["active_source_runtime_migration_readiness_gate"] = (
        asrmrg_svc.build_active_source_runtime_migration_readiness_gate(None)
    )
    out["active_source_runtime_migration_dry_run_command_package"] = (
        asrmdrcp_svc.build_active_source_runtime_migration_dry_run_command_package(None)
    )
    out["active_source_runtime_migration_apply_execution_read_only"] = (
        asrmrae_svc.build_discovery_read_only_apply_execution_status_attachment()
    )
    out["active_source_runtime_migration_post_apply_verification_read_only"] = (
        asrmrpav_svc.build_discovery_read_only_post_apply_verification_status_attachment()
    )
    n_active_opportunity_sources = asesrm_svc.count_nf_active_opportunity_sources_readonly(
        session,
        organization_id=org_id,
    )
    out["active_source_empty_state_read_model"] = (
        asesrm_svc.build_discovery_read_only_active_source_empty_state_attachment(
            observed_active_source_count=n_active_opportunity_sources,
            organization_id=org_id,
        )
    )
    out["active_source_creation_request"] = (
        ascrcreq_svc.build_discovery_read_only_active_source_creation_request_attachment()
    )
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
