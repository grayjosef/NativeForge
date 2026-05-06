"""Sprint 16: deterministic discovery coverage gap intelligence (offline engine)."""

from __future__ import annotations

import hashlib
import uuid
from collections import Counter
from copy import deepcopy
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from nativeforge.db.models import (
    NfDiscoveryIntakeCandidate,
    NfDiscoveryReviewItem,
    NfOpportunitySource,
)
from nativeforge.domain.enums import (
    CoverageGapSeverity,
    CoverageGapType,
    CoverageRecommendationAction,
    FundingDomain,
    OpportunitySourceType,
    OpportunityVerificationStatus,
    SourceHealthStatus,
    SourcePriorityLevel,
    SourceReliabilityRating,
    TribalEntityType,
)
from nativeforge.lib.demo_isolation import OrgType
from nativeforge.repositories import opportunity_sources as os_repo
from nativeforge.services import opportunity_discovery_service as ods
from nativeforge.services import source_freshness_service as sfs

# Stable API contract version (also exposed as coverage_gap_intel_version).
SCHEMA_VERSION = "nf_discovery_coverage_gap_intelligence_v1"
COVERAGE_GAP_INTEL_VERSION = SCHEMA_VERSION

_PRIORITY_ALERT_LEVELS = frozenset(
    {
        SourcePriorityLevel.high.value,
        SourcePriorityLevel.critical.value,
    }
)

_CRITICAL_SOURCE_TYPES = frozenset(
    {
        OpportunitySourceType.federal.value,
        OpportunitySourceType.state.value,
        OpportunitySourceType.tribal.value,
    }
)

_HIGH_IMPACT_DOMAINS = frozenset(
    {
        FundingDomain.climate_resilience.value,
        FundingDomain.language_culture.value,
        FundingDomain.education.value,
        FundingDomain.health.value,
    }
)

_PRIORITY_STATE_CODES = frozenset(
    {
        "AK",
        "AZ",
        "CA",
        "MN",
        "MT",
        "NM",
        "ND",
        "OK",
        "OR",
        "SD",
        "WA",
        "WI",
    }
)

_PRIORITY_REGION_KEYS = frozenset(
    {
        "southwest",
        "great_plains",
        "pacific_northwest",
        "alaska",
        "great_lakes",
        "national_capital",
    }
)

_PRIORITY_TRIBAL_GROUP_KEYS = frozenset(
    {
        "native_communities_general",
        "tribal_colleges",
        "urban_indian",
        "remote_native_villages",
    }
)

_MIN_CANDIDATES_FOR_YIELD = 8
_ACCEPTANCE_RATIO_WARN = 0.18
_OPEN_REVIEW_BURDEN_THRESHOLD = 4

_FAILURE_STREAK_THRESHOLD = 3
_EMPTY_STREAK_THRESHOLD = 3

_PRIORITY_APPLICANT_TYPES = (
    TribalEntityType.federally_recognized_tribe,
    TribalEntityType.tribal_government,
    TribalEntityType.tribal_nonprofit,
    TribalEntityType.alaska_native_corporation,
    TribalEntityType.native_serving_nonprofit,
)

_COVERAGE_GAP_TYPES_FOR_COVERAGE_SCORE = frozenset(
    {
        CoverageGapType.missing_source_type.value,
        CoverageGapType.undercovered_domain.value,
        CoverageGapType.undercovered_applicant_type.value,
        CoverageGapType.undercovered_state.value,
        CoverageGapType.undercovered_region.value,
        CoverageGapType.undercovered_tribal_group.value,
    }
)


def _gap_id(*parts: str) -> str:
    payload = "|".join(parts)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:22]


def _recommendation_id(gap_id: str) -> str:
    return hashlib.sha256(f"rec|{gap_id}".encode()).hexdigest()[:22]


def _severity_rank(sev: str) -> int:
    order = {
        CoverageGapSeverity.critical.value: 0,
        CoverageGapSeverity.high.value: 1,
        CoverageGapSeverity.medium.value: 2,
        CoverageGapSeverity.low.value: 3,
    }
    return order.get(sev, 9)


def _collect_applicant_tokens(rows: list[NfOpportunitySource]) -> dict[str, int]:
    hist: dict[str, int] = {}
    for r in rows:
        if not r.is_active:
            continue
        raw = r.applicant_types_json
        tokens: set[str] = set()
        if isinstance(raw, list):
            for x in raw:
                tokens.add(str(x).strip().lower())
        elif isinstance(raw, dict):
            for k in raw.keys():
                tokens.add(str(k).strip().lower())
        for t in tokens:
            hist[t] = hist.get(t, 0) + 1
    return hist


def _collect_state_codes(rows: list[NfOpportunitySource]) -> dict[str, int]:
    hist: dict[str, int] = {}
    for r in rows:
        if not r.is_active:
            continue
        cs = r.covered_states_json
        if not isinstance(cs, list):
            continue
        for x in cs:
            code = str(x).strip().upper()[:8]
            if code:
                hist[code] = hist.get(code, 0) + 1
    return hist


def _collect_region_keys(rows: list[NfOpportunitySource]) -> dict[str, int]:
    hist: dict[str, int] = {}
    for r in rows:
        if not r.is_active:
            continue
        cr = r.covered_regions_json
        if not isinstance(cr, list):
            continue
        for x in cr:
            key = str(x).strip().lower()
            if key:
                hist[key] = hist.get(key, 0) + 1
    return hist


def _collect_tribal_group_keys(rows: list[NfOpportunitySource]) -> dict[str, int]:
    hist: dict[str, int] = {}
    for r in rows:
        if not r.is_active:
            continue
        tg = r.covered_tribal_groups_json
        if not isinstance(tg, list):
            continue
        for x in tg:
            key = str(x).strip().lower()
            if key:
                hist[key] = hist.get(key, 0) + 1
    return hist


def _intake_stats_by_source(
    session: Session,
    *,
    org_id: uuid.UUID,
    org_type: OrgType,
) -> dict[uuid.UUID, dict[str, int]]:
    is_demo = org_type == "demo"
    stmt = (
        select(
            NfDiscoveryIntakeCandidate.source_registry_id,
            NfDiscoveryIntakeCandidate.candidate_status,
            func.count().label("n"),
        )
        .where(
            NfDiscoveryIntakeCandidate.organization_id == org_id,
            NfDiscoveryIntakeCandidate.is_demo.is_(is_demo),
            NfDiscoveryIntakeCandidate.source_registry_id.isnot(None),
        )
        .group_by(
            NfDiscoveryIntakeCandidate.source_registry_id,
            NfDiscoveryIntakeCandidate.candidate_status,
        )
    )
    out: dict[uuid.UUID, dict[str, int]] = {}
    for sid, status, n in session.execute(stmt):
        assert sid is not None
        bucket = out.setdefault(sid, {})
        bucket[str(status)] = int(n)
    return out


def _open_review_counts_by_source(
    session: Session,
    *,
    org_id: uuid.UUID,
    org_type: OrgType,
) -> dict[uuid.UUID, int]:
    is_demo = org_type == "demo"
    stmt = (
        select(NfDiscoveryReviewItem.source_registry_id, func.count().label("n"))
        .where(
            NfDiscoveryReviewItem.organization_id == org_id,
            NfDiscoveryReviewItem.is_demo.is_(is_demo),
            NfDiscoveryReviewItem.source_registry_id.isnot(None),
            NfDiscoveryReviewItem.review_status.in_(
                ["open", "in_review"],
            ),
        )
        .group_by(NfDiscoveryReviewItem.source_registry_id)
    )
    return {sid: int(n) for sid, n in session.execute(stmt) if sid is not None}


def _penalty_weight(sev: str) -> int:
    return {
        CoverageGapSeverity.critical.value: 18,
        CoverageGapSeverity.high.value: 12,
        CoverageGapSeverity.medium.value: 7,
        CoverageGapSeverity.low.value: 3,
    }.get(sev, 5)


def _score_coverage_from_gaps(gaps: list[dict[str, Any]]) -> int:
    cov_gaps = [
        g for g in gaps if g["gap_type"] in _COVERAGE_GAP_TYPES_FOR_COVERAGE_SCORE
    ]
    penalty = sum(_penalty_weight(g["severity"]) for g in cov_gaps)
    return max(0, min(100, 100 - min(100, penalty)))


def _score_freshness(rows: list[NfOpportunitySource]) -> int:
    active = [r for r in rows if r.is_active]
    if not active:
        return 100
    bad_health = frozenset(
        {
            SourceHealthStatus.stale.value,
            SourceHealthStatus.degraded.value,
            SourceHealthStatus.failing.value,
            SourceHealthStatus.attention_needed.value,
        }
    )
    bad = sum(1 for r in active if r.source_health_status in bad_health)
    return max(0, 100 - round(100 * bad / len(active)))


def _score_reliability(rows: list[NfOpportunitySource]) -> int:
    active = [r for r in rows if r.is_active]
    if not active:
        return 100
    weak = frozenset(
        {
            SourceReliabilityRating.unknown.value,
            SourceReliabilityRating.low.value,
        }
    )
    n_weak = sum(1 for r in active if r.reliability_rating in weak)
    return max(0, 100 - round(100 * n_weak / len(active)))


def _score_yield(
    rows: list[NfOpportunitySource],
    intake_by_src: dict[uuid.UUID, dict[str, int]],
) -> int:
    ratios: list[float] = []
    for r in rows:
        if not r.is_active:
            continue
        bucket = intake_by_src.get(r.id, {})
        total = sum(bucket.values())
        if total < _MIN_CANDIDATES_FOR_YIELD:
            continue
        accepted = bucket.get("accepted", 0)
        ratios.append(accepted / total)
    if not ratios:
        return 82
    avg = sum(ratios) / len(ratios)
    return max(0, min(100, round(100 * avg)))


def _score_review_burden(review_open: dict[uuid.UUID, int]) -> int:
    total_open = sum(review_open.values())
    return min(100, total_open * 9)


def _rollup_from_gaps(
    gaps: list[dict[str, Any]],
    *,
    source_row_count: int,
) -> dict[str, Any]:
    by_sev = Counter(g["severity"] for g in gaps)
    by_type = Counter(g["gap_type"] for g in gaps)
    return {
        "source_row_count": source_row_count,
        "gap_count": len(gaps),
        "by_severity": dict(by_sev),
        "by_gap_type": dict(by_type),
    }


def _rationale_for_gap(g: dict[str, Any]) -> str:
    gt = g["gap_type"]
    d = g.get("detail") or {}
    if gt == CoverageGapType.missing_source_type.value:
        return (
            f"No active registry row lists source_type={d.get('source_type')!r}; "
            "add or activate a source that monitors this channel."
        )
    if gt == CoverageGapType.undercovered_domain.value:
        return (
            f"No sources tag funding_domain={d.get('funding_domain')!r}; "
            "expand registry coverage for this domain."
        )
    if gt == CoverageGapType.undercovered_applicant_type.value:
        return (
            "Applicant coverage metadata does not reference "
            f"applicant_type={d.get('applicant_type')!r}."
        )
    if gt == CoverageGapType.undercovered_state.value:
        return f"No sources list covered_states_json including {d.get('state_code')!r}."
    if gt == CoverageGapType.undercovered_region.value:
        return f"No sources tag covered_regions_json with key {d.get('region_key')!r}."
    if gt == CoverageGapType.undercovered_tribal_group.value:
        return (
            f"No sources tag covered_tribal_groups_json with key "
            f"{d.get('tribal_group_key')!r}."
        )
    if gt == CoverageGapType.stale_priority_source.value:
        return (
            "High-priority source health is stale; tighten scheduling or complete "
            "recent checks."
        )
    if gt == CoverageGapType.degraded_priority_source.value:
        return (
            "High-priority source health is degraded; review check outcomes and "
            "registry metadata."
        )
    if gt == CoverageGapType.attention_needed_priority_source.value:
        return "High-priority source requires operator attention per registry health."
    if gt == CoverageGapType.failing_priority_source.value:
        return (
            "High-priority source health is failing; investigate errors and "
            "corrective action."
        )
    if gt == CoverageGapType.low_reliability_source.value:
        return (
            "Reliability rating is weak or unknown for this registry row; verify "
            "trustworthiness."
        )
    if gt == CoverageGapType.unverified_priority_source.value:
        return "High-priority source remains unverified; complete operator review."
    if gt == CoverageGapType.low_yield_source.value:
        return (
            "Intake acceptance ratio is low relative to candidate volume; "
            "review upstream matching."
        )
    if gt == CoverageGapType.high_review_burden_source.value:
        return "Too many open discovery review items are attributed to this source."
    if gt == CoverageGapType.repeated_failed_checks.value:
        return (
            f"Registry shows consecutive_failure_count="
            f"{d.get('consecutive_failure_count')} from recent check bookkeeping."
        )
    if gt == CoverageGapType.repeated_empty_checks.value:
        return (
            f"Registry shows consecutive_empty_check_count="
            f"{d.get('consecutive_empty_check_count')} from recent empty outcomes."
        )
    return "Coverage intelligence derived from local registry and intake metadata."


def _gaps_to_recommendations(
    gaps: list[dict[str, Any]],
    rows_by_id: dict[str, NfOpportunitySource],
) -> list[dict[str, Any]]:
    sorted_gaps = sorted(
        gaps,
        key=lambda x: (_severity_rank(x["severity"]), x["title"]),
    )
    out: list[dict[str, Any]] = []
    for rank, g in enumerate(sorted_gaps, start=1):
        detail = g.get("detail") or {}
        sid = detail.get("source_id")
        src = rows_by_id.get(str(sid)) if sid else None
        out.append(
            {
                "recommendation_id": _recommendation_id(str(g["gap_id"])),
                "gap_id": str(g["gap_id"]),
                "gap_type": g["gap_type"],
                "action": g["recommendation_action"],
                "severity": g["severity"],
                "title": g["title"],
                "rationale": _rationale_for_gap(g),
                "source_registry_id": sid,
                "source_name": src.source_name if src else None,
                "funding_domain": detail.get("funding_domain"),
                "source_type": detail.get("source_type"),
                "operator_action": g["recommendation_action"],
                "rank": rank,
            }
        )
    return out


def _collect_raw_gaps(
    rows: list[NfOpportunitySource],
    base: dict[str, Any],
    intake_by_src: dict[uuid.UUID, dict[str, int]],
    review_open: dict[uuid.UUID, int],
) -> list[dict[str, Any]]:
    gaps: list[dict[str, Any]] = []

    for st in base["source_type_gaps_in_registry"]:
        sev = (
            CoverageGapSeverity.critical.value
            if st in _CRITICAL_SOURCE_TYPES
            else CoverageGapSeverity.high.value
        )
        gaps.append(
            {
                "gap_id": _gap_id(CoverageGapType.missing_source_type.value, st),
                "gap_type": CoverageGapType.missing_source_type.value,
                "severity": sev,
                "recommendation_action": CoverageRecommendationAction.add_source.value,
                "title": f"No registered source for source_type={st}",
                "detail": {"source_type": st},
            }
        )

    for d in base["funding_domain_gaps_in_registry"]:
        sev = (
            CoverageGapSeverity.high.value
            if d in _HIGH_IMPACT_DOMAINS
            else CoverageGapSeverity.medium.value
        )
        gaps.append(
            {
                "gap_id": _gap_id(CoverageGapType.undercovered_domain.value, d),
                "gap_type": CoverageGapType.undercovered_domain.value,
                "severity": sev,
                "recommendation_action": (
                    CoverageRecommendationAction.expand_domain_coverage.value
                ),
                "title": f"No sources tag funding domain '{d}'",
                "detail": {"funding_domain": d},
            }
        )

    applicant_hist = _collect_applicant_tokens(rows)
    for te in _PRIORITY_APPLICANT_TYPES:
        k = te.value
        if applicant_hist.get(k, 0) == 0:
            gaps.append(
                {
                    "gap_id": _gap_id(
                        CoverageGapType.undercovered_applicant_type.value, k
                    ),
                    "gap_type": CoverageGapType.undercovered_applicant_type.value,
                    "severity": CoverageGapSeverity.medium.value,
                    "recommendation_action": (
                        CoverageRecommendationAction.expand_domain_coverage.value
                    ),
                    "title": f"No sources mention applicant_type '{k}'",
                    "detail": {"applicant_type": k},
                }
            )

    state_hist = _collect_state_codes(rows)
    for code in sorted(_PRIORITY_STATE_CODES):
        if state_hist.get(code, 0) == 0:
            gaps.append(
                {
                    "gap_id": _gap_id(CoverageGapType.undercovered_state.value, code),
                    "gap_type": CoverageGapType.undercovered_state.value,
                    "severity": CoverageGapSeverity.medium.value,
                    "recommendation_action": (
                        CoverageRecommendationAction.expand_geographic_coverage.value
                    ),
                    "title": f"No sources cover priority state {code}",
                    "detail": {"state_code": code},
                }
            )

    region_hist = _collect_region_keys(rows)
    for rk in sorted(_PRIORITY_REGION_KEYS):
        if region_hist.get(rk, 0) == 0:
            gaps.append(
                {
                    "gap_id": _gap_id(CoverageGapType.undercovered_region.value, rk),
                    "gap_type": CoverageGapType.undercovered_region.value,
                    "severity": CoverageGapSeverity.medium.value,
                    "recommendation_action": (
                        CoverageRecommendationAction.expand_geographic_coverage.value
                    ),
                    "title": f"No sources tag coverage region '{rk}'",
                    "detail": {"region_key": rk},
                }
            )

    tg_hist = _collect_tribal_group_keys(rows)
    for tk in sorted(_PRIORITY_TRIBAL_GROUP_KEYS):
        if tg_hist.get(tk, 0) == 0:
            gaps.append(
                {
                    "gap_id": _gap_id(
                        CoverageGapType.undercovered_tribal_group.value, tk
                    ),
                    "gap_type": CoverageGapType.undercovered_tribal_group.value,
                    "severity": CoverageGapSeverity.medium.value,
                    "recommendation_action": (
                        CoverageRecommendationAction.expand_geographic_coverage.value
                    ),
                    "title": f"No sources tag tribal group '{tk}'",
                    "detail": {"tribal_group_key": tk},
                }
            )

    for r in rows:
        if not r.is_active:
            continue
        sid = str(r.id)
        pr = r.priority_level
        health = r.source_health_status

        if r.consecutive_failure_count >= _FAILURE_STREAK_THRESHOLD:
            gaps.append(
                {
                    "gap_id": _gap_id(
                        CoverageGapType.repeated_failed_checks.value, sid
                    ),
                    "gap_type": CoverageGapType.repeated_failed_checks.value,
                    "severity": CoverageGapSeverity.high.value,
                    "recommendation_action": (
                        CoverageRecommendationAction.review_source_quality.value
                    ),
                    "title": (f"Repeated failed checks recorded for {r.source_name}"),
                    "detail": {
                        "source_id": sid,
                        "priority_level": pr,
                        "consecutive_failure_count": r.consecutive_failure_count,
                    },
                }
            )

        if r.consecutive_empty_check_count >= _EMPTY_STREAK_THRESHOLD:
            gaps.append(
                {
                    "gap_id": _gap_id(CoverageGapType.repeated_empty_checks.value, sid),
                    "gap_type": CoverageGapType.repeated_empty_checks.value,
                    "severity": CoverageGapSeverity.medium.value,
                    "recommendation_action": (
                        CoverageRecommendationAction.review_source_quality.value
                    ),
                    "title": (f"Repeated empty checks recorded for {r.source_name}"),
                    "detail": {
                        "source_id": sid,
                        "priority_level": pr,
                        "consecutive_empty_check_count": (
                            r.consecutive_empty_check_count
                        ),
                    },
                }
            )

        if pr in _PRIORITY_ALERT_LEVELS:
            if health == SourceHealthStatus.stale.value:
                gaps.append(
                    {
                        "gap_id": _gap_id(
                            CoverageGapType.stale_priority_source.value, sid
                        ),
                        "gap_type": CoverageGapType.stale_priority_source.value,
                        "severity": CoverageGapSeverity.high.value,
                        "recommendation_action": (
                            CoverageRecommendationAction.increase_check_frequency.value
                        ),
                        "title": f"High-priority source is stale: {r.source_name}",
                        "detail": {
                            "source_id": sid,
                            "priority_level": pr,
                            "source_health_status": health,
                        },
                    }
                )
            if health == SourceHealthStatus.degraded.value:
                gaps.append(
                    {
                        "gap_id": _gap_id(
                            CoverageGapType.degraded_priority_source.value, sid
                        ),
                        "gap_type": CoverageGapType.degraded_priority_source.value,
                        "severity": CoverageGapSeverity.high.value,
                        "recommendation_action": (
                            CoverageRecommendationAction.review_source_quality.value
                        ),
                        "title": (f"High-priority source is degraded: {r.source_name}"),
                        "detail": {
                            "source_id": sid,
                            "priority_level": pr,
                            "source_health_status": health,
                        },
                    }
                )
            if health == SourceHealthStatus.attention_needed.value:
                gaps.append(
                    {
                        "gap_id": _gap_id(
                            CoverageGapType.attention_needed_priority_source.value,
                            sid,
                        ),
                        "gap_type": (
                            CoverageGapType.attention_needed_priority_source.value
                        ),
                        "severity": CoverageGapSeverity.high.value,
                        "recommendation_action": (
                            CoverageRecommendationAction.review_source_quality.value
                        ),
                        "title": (
                            f"High-priority source needs attention: {r.source_name}"
                        ),
                        "detail": {
                            "source_id": sid,
                            "priority_level": pr,
                            "source_health_status": health,
                        },
                    }
                )
            if health == SourceHealthStatus.failing.value:
                gaps.append(
                    {
                        "gap_id": _gap_id(
                            CoverageGapType.failing_priority_source.value, sid
                        ),
                        "gap_type": CoverageGapType.failing_priority_source.value,
                        "severity": CoverageGapSeverity.critical.value,
                        "recommendation_action": (
                            CoverageRecommendationAction.review_source_quality.value
                        ),
                        "title": (
                            f"High-priority source is failing checks: {r.source_name}"
                        ),
                        "detail": {
                            "source_id": sid,
                            "priority_level": pr,
                            "source_health_status": health,
                        },
                    }
                )
            if r.reliability_rating == SourceReliabilityRating.unknown.value:
                gaps.append(
                    {
                        "gap_id": _gap_id(
                            CoverageGapType.low_reliability_source.value,
                            sid,
                            "unknown",
                        ),
                        "gap_type": CoverageGapType.low_reliability_source.value,
                        "severity": CoverageGapSeverity.medium.value,
                        "recommendation_action": (
                            CoverageRecommendationAction.verify_source.value
                        ),
                        "title": (
                            f"High-priority source has unknown reliability: "
                            f"{r.source_name}"
                        ),
                        "detail": {
                            "source_id": sid,
                            "priority_level": pr,
                            "reliability_rating": r.reliability_rating,
                        },
                    }
                )
            if r.reliability_rating == SourceReliabilityRating.low.value:
                gaps.append(
                    {
                        "gap_id": _gap_id(
                            CoverageGapType.low_reliability_source.value,
                            sid,
                            "low",
                        ),
                        "gap_type": CoverageGapType.low_reliability_source.value,
                        "severity": CoverageGapSeverity.medium.value,
                        "recommendation_action": (
                            CoverageRecommendationAction.verify_source.value
                        ),
                        "title": (
                            f"High-priority source has low reliability: {r.source_name}"
                        ),
                        "detail": {
                            "source_id": sid,
                            "priority_level": pr,
                            "reliability_rating": r.reliability_rating,
                        },
                    }
                )
            if r.verification_status == OpportunityVerificationStatus.unverified.value:
                gaps.append(
                    {
                        "gap_id": _gap_id(
                            CoverageGapType.unverified_priority_source.value, sid
                        ),
                        "gap_type": CoverageGapType.unverified_priority_source.value,
                        "severity": CoverageGapSeverity.high.value,
                        "recommendation_action": (
                            CoverageRecommendationAction.verify_source.value
                        ),
                        "title": (
                            f"High-priority source is still unverified: {r.source_name}"
                        ),
                        "detail": {
                            "source_id": sid,
                            "priority_level": pr,
                            "verification_status": r.verification_status,
                        },
                    }
                )

        if (
            r.reliability_rating == SourceReliabilityRating.low.value
            and pr not in _PRIORITY_ALERT_LEVELS
        ):
            gaps.append(
                {
                    "gap_id": _gap_id(
                        CoverageGapType.low_reliability_source.value, sid, "any_low"
                    ),
                    "gap_type": CoverageGapType.low_reliability_source.value,
                    "severity": CoverageGapSeverity.low.value,
                    "recommendation_action": (
                        CoverageRecommendationAction.verify_source.value
                    ),
                    "title": f"Source has low reliability rating: {r.source_name}",
                    "detail": {
                        "source_id": sid,
                        "priority_level": pr,
                        "reliability_rating": r.reliability_rating,
                    },
                }
            )

        bucket = intake_by_src.get(r.id, {})
        total_cand = sum(bucket.values())
        accepted = bucket.get("accepted", 0)
        if total_cand >= _MIN_CANDIDATES_FOR_YIELD and total_cand > 0:
            ratio = accepted / total_cand
            if ratio < _ACCEPTANCE_RATIO_WARN:
                gaps.append(
                    {
                        "gap_id": _gap_id(CoverageGapType.low_yield_source.value, sid),
                        "gap_type": CoverageGapType.low_yield_source.value,
                        "severity": CoverageGapSeverity.medium.value,
                        "recommendation_action": (
                            CoverageRecommendationAction.review_source_quality.value
                        ),
                        "title": (
                            "Low acceptance ratio from intake for source "
                            f"{r.source_name}"
                        ),
                        "detail": {
                            "source_id": sid,
                            "accepted_count": accepted,
                            "candidate_total": total_cand,
                            "acceptance_ratio": round(ratio, 4),
                        },
                    }
                )

        rev_n = review_open.get(r.id, 0)
        if rev_n >= _OPEN_REVIEW_BURDEN_THRESHOLD:
            gaps.append(
                {
                    "gap_id": _gap_id(
                        CoverageGapType.high_review_burden_source.value, sid
                    ),
                    "gap_type": CoverageGapType.high_review_burden_source.value,
                    "severity": CoverageGapSeverity.high.value,
                    "recommendation_action": (
                        CoverageRecommendationAction.review_source_quality.value
                    ),
                    "title": (
                        f"Elevated open discovery review burden for {r.source_name}"
                    ),
                    "detail": {
                        "source_id": sid,
                        "open_review_items": rev_n,
                    },
                }
            )

    seen: set[str] = set()
    deduped: list[dict[str, Any]] = []
    for g in sorted(gaps, key=lambda x: (_severity_rank(x["severity"]), x["title"])):
        gid = str(g["gap_id"])
        if gid in seen:
            continue
        seen.add(gid)
        deduped.append(g)

    return deduped


def _gap_matches_filters(
    g: dict[str, Any],
    *,
    severity: str | None,
    gap_type: str | None,
    domain: str | None,
    source_type: str | None,
    priority_level: str | None,
) -> bool:
    if severity is not None and g["severity"] != severity:
        return False
    if gap_type is not None and g["gap_type"] != gap_type:
        return False
    detail = g.get("detail") or {}
    if domain is not None and detail.get("funding_domain") != domain:
        return False
    if source_type is not None:
        st = detail.get("source_type")
        if st != source_type:
            return False
    if priority_level is not None and detail.get("priority_level") != priority_level:
        return False
    return True


def filter_coverage_gap_payload(
    payload: dict[str, Any],
    *,
    rows_by_id: dict[str, NfOpportunitySource],
    severity: str | None = None,
    gap_type: str | None = None,
    domain: str | None = None,
    source_type: str | None = None,
    priority_level: str | None = None,
    limit: int | None = None,
    adjust_summary_rollup: bool = True,
) -> dict[str, Any]:
    """Return a shallow copy with filtered gaps/recommendations (scores unchanged)."""
    fgaps = [
        g
        for g in payload["coverage_gaps"]
        if _gap_matches_filters(
            g,
            severity=severity,
            gap_type=gap_type,
            domain=domain,
            source_type=source_type,
            priority_level=priority_level,
        )
    ]
    if limit is not None:
        fgaps = fgaps[:limit]
    frecs = _gaps_to_recommendations(fgaps, rows_by_id)
    out = deepcopy(payload)
    out["coverage_gaps"] = fgaps
    out["source_recommendations"] = frecs
    out["operator_next_actions"] = list(frecs)
    if adjust_summary_rollup:
        src_ct = payload["summary"]["rollup"]["source_row_count"]
        out["summary"] = {
            **payload["summary"],
            "rollup": _rollup_from_gaps(fgaps, source_row_count=src_ct),
        }
    return out


def build_coverage_gap_intelligence(
    session: Session,
    *,
    org_id: uuid.UUID,
    org_type: OrgType,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Full deterministic intelligence payload for operators (offline)."""
    ref_now = now or datetime.now(UTC)
    rows = os_repo.list_opportunity_sources_for_org(
        session=session,
        org_id=org_id,
        org_type=org_type,
    )
    base = ods.discovery_coverage_summary(rows)
    intake_by_src = _intake_stats_by_source(session, org_id=org_id, org_type=org_type)
    review_open = _open_review_counts_by_source(
        session, org_id=org_id, org_type=org_type
    )

    deduped = _collect_raw_gaps(rows, base, intake_by_src, review_open)
    rows_by_id = {str(r.id): r for r in rows}

    coverage_score = _score_coverage_from_gaps(deduped)
    freshness_score = _score_freshness(rows)
    reliability_score = _score_reliability(rows)
    yield_score = _score_yield(rows, intake_by_src)
    review_burden_score = _score_review_burden(review_open)

    rollup_full = _rollup_from_gaps(deduped, source_row_count=base["source_row_count"])

    source_intel_snapshot = [
        {
            "source_id": str(r.id),
            "source_name": r.source_name,
            "priority_level": r.priority_level,
            "source_health_status": r.source_health_status,
            "effective_next_check_due_at": (
                sfs.effective_next_deadline(r, now=ref_now).isoformat()
                if sfs.effective_next_deadline(r, now=ref_now)
                else None
            ),
            "intake_candidate_totals": intake_by_src.get(r.id, {}),
            "open_discovery_review_items": review_open.get(r.id, 0),
        }
        for r in rows
        if r.is_active
    ]

    recommendations = _gaps_to_recommendations(deduped, rows_by_id)

    summary = {
        "rollup": rollup_full,
        "coverage_summary_ref": {
            "coverage_summary_version": base["coverage_summary_version"],
            "source_type_gaps_in_registry": base["source_type_gaps_in_registry"],
            "funding_domain_gaps_in_registry": base["funding_domain_gaps_in_registry"],
        },
        "active_source_count": sum(1 for r in rows if r.is_active),
        "scores": {
            "coverage_score": coverage_score,
            "freshness_score": freshness_score,
            "reliability_score": reliability_score,
            "yield_score": yield_score,
            "review_burden_score": review_burden_score,
        },
    }

    is_demo = org_type == "demo"
    return {
        "schema_version": SCHEMA_VERSION,
        "coverage_gap_intel_version": COVERAGE_GAP_INTEL_VERSION,
        "organization_id": str(org_id),
        "is_demo": is_demo,
        "generated_at": ref_now.isoformat(),
        "coverage_score": coverage_score,
        "freshness_score": freshness_score,
        "reliability_score": reliability_score,
        "yield_score": yield_score,
        "review_burden_score": review_burden_score,
        "summary": summary,
        "coverage_gaps": deduped,
        "source_recommendations": recommendations,
        "operator_next_actions": list(recommendations),
        "coverage_summary_ref": summary["coverage_summary_ref"],
        "rollup": rollup_full,
        "organization_scope": {"org_id": str(org_id), "plane": org_type},
        "source_yield_snapshot": sorted(
            source_intel_snapshot,
            key=lambda x: x["source_name"].lower(),
        ),
        # Legacy shape for callers/tests expecting `gaps`:
        "gaps": deduped,
    }


def coverage_gap_intel_summary_compact(payload: dict[str, Any]) -> dict[str, Any]:
    """Smaller dict for exports / embedding."""
    summary = payload.get("summary") or {}
    rollup = summary.get("rollup") or payload.get("rollup") or {}
    scores = summary.get("scores") or {}
    return {
        "schema_version": payload.get("schema_version"),
        "coverage_gap_intel_version": payload.get("coverage_gap_intel_version"),
        "generated_at": payload.get("generated_at"),
        "rollup": rollup,
        "coverage_summary_ref": summary.get("coverage_summary_ref")
        or payload.get("coverage_summary_ref"),
        "scores": scores,
    }
