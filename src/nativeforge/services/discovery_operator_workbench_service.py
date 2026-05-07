"""Sprint 17: Discovery Operator Workbench — unified decision pack (offline engine)."""

from __future__ import annotations

import copy
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import Session

from nativeforge.db.models import NfOpportunitySource
from nativeforge.domain.enums import (
    CoverageGapType,
    DiscoveryReviewItemType,
    OperatorDecisionAction,
    OperatorDecisionItemType,
    OperatorDecisionSeverity,
    SourceHealthStatus,
    SourcePriorityLevel,
)
from nativeforge.lib.demo_isolation import OrgType
from nativeforge.repositories import discovery_intake_runs as intake_repo
from nativeforge.repositories import source_check_runs as scr_repo
from nativeforge.services import discovery_coverage_gap_service as dcg_svc
from nativeforge.services import discovery_intake_service as d_intake
from nativeforge.services import discovery_review_service as d_review
from nativeforge.services import opportunity_discovery_service as ods
from nativeforge.services import source_freshness_service as sfs
from nativeforge.services.discovery_operator_workbench_pure import (
    decision_id as _decision_id,
)
from nativeforge.services.discovery_operator_workbench_pure import (
    map_coverage_action_to_operator as _map_coverage_action_to_operator,
)
from nativeforge.services.discovery_operator_workbench_pure import (
    review_queue_item_type as _review_queue_item_type,
)
from nativeforge.services.discovery_operator_workbench_pure import (
    severity_from_coverage as _severity_from_coverage,
)

DECISION_PACK_SCHEMA_VERSION = "nf_discovery_operator_decision_pack_v1"
WORKBENCH_CONNECTOR_INTEL_SCHEMA_VERSION = "nf_workbench_connector_intelligence_v1"

_CONNECTOR_HEALTH_BUCKETS: tuple[str, ...] = (
    "healthy",
    "empty",
    "degraded",
    "failed",
    "stale",
    "unknown",
)


def _is_connector_result_summary(rs: Any) -> bool:
    if not isinstance(rs, dict):
        return False
    if rs.get("connector_result_summary_schema_version"):
        return True
    return rs.get("manifest") is not None and rs.get("health_status") is not None


def _manifest_counts_from_rs(rs: dict[str, Any]) -> dict[str, Any]:
    mc = rs.get("manifest_counts")
    if isinstance(mc, dict):
        return mc
    man = rs.get("manifest")
    if isinstance(man, dict):
        c = man.get("counts")
        if isinstance(c, dict):
            return c
    return {}


def _dt_iso(v: Any) -> str | None:
    if v is None:
        return None
    if isinstance(v, datetime):
        return v.isoformat()
    return str(v)


def _registry_health_rollups(source_rows: list[NfOpportunitySource]) -> dict[str, int]:
    keys = (
        SourceHealthStatus.healthy.value,
        SourceHealthStatus.degraded.value,
        SourceHealthStatus.failing.value,
        SourceHealthStatus.stale.value,
        SourceHealthStatus.attention_needed.value,
        SourceHealthStatus.unknown.value,
    )
    out: dict[str, int] = dict.fromkeys(keys, 0)
    out["other"] = 0
    for r in source_rows:
        if not r.is_active:
            continue
        raw = r.source_health_status
        h = (str(raw).strip() if raw else "") or SourceHealthStatus.unknown.value
        if h in out:
            out[h] += 1
        else:
            out["other"] += 1
    if out["other"] == 0:
        out.pop("other")
    return out


def _pressure_tags(
    rs: dict[str, Any],
    registry_health: str | None,
    *,
    duplicate_heavy: bool,
    review_heavy: bool,
) -> list[str]:
    tags: set[str] = set()
    hc = str(rs.get("health_status") or "").strip().lower()
    rh = (registry_health or "").strip().lower()
    codes = [str(c).lower() for c in (rs.get("warning_codes") or [])]

    if hc == "stale" or rh == SourceHealthStatus.stale.value:
        tags.add("source_freshness")
    if rh == SourceHealthStatus.attention_needed.value:
        tags.add("source_freshness")
    if any("overdue" in c for c in codes):
        tags.add("source_freshness")

    if hc in {"failed", "degraded", "empty"}:
        tags.add("connector_quality")
    if any("fixture_normalization" in c or "normalization" in c for c in codes):
        tags.add("connector_quality")
    if any("connector_run_empty" in c for c in codes):
        tags.add("connector_quality")

    cnt = rs.get("counts") if isinstance(rs.get("counts"), dict) else {}
    acc = int(cnt.get("accepted_count") or 0)
    dup = int(cnt.get("duplicate_count") or 0)
    rej = int(cnt.get("rejected_count") or 0)
    err = int(cnt.get("error_count") or 0)
    rr = int(cnt.get("review_required_count") or 0)
    tot = acc + dup + rej + err
    if duplicate_heavy:
        tags.add("duplicate_saturation")
    if review_heavy:
        tags.add("native_relevance_precision")
    elif tot >= 4 and rr >= max(2, int(0.28 * tot)):
        tags.add("native_relevance_precision")

    return sorted(tags)


def _attention_line(
    rs: dict[str, Any],
    registry_health: str | None,
    diag: str,
    esc_list: list[Any],
) -> str:
    parts: list[str] = []
    rh = (registry_health or "").strip()
    if rh and rh != SourceHealthStatus.healthy.value:
        parts.append(f"Registry health is {rh}.")
    hc = str(rs.get("health_status") or "").strip()
    if hc and hc != "healthy":
        parts.append(f"Latest connector check classified as {hc}.")
    if diag:
        parts.append(diag)
    if esc_list and isinstance(esc_list[0], dict):
        t = str(esc_list[0].get("operator_title") or "").strip()
        if t:
            parts.append(f"Recommended follow-up: {t}.")
    return " ".join(parts).strip() or (
        "Latest stored connector summary looks nominal for this source."
    )


def build_workbench_connector_intelligence(
    session: Session,
    *,
    org_id: uuid.UUID,
    org_type: OrgType,
    source_rows: list[NfOpportunitySource],
    now: datetime,
    check_run_limit: int = 4000,
) -> dict[str, Any]:
    """Roll up connector/source-check intelligence from persisted summaries."""
    lim = max(1, min(int(check_run_limit), 8000))
    src_meta: dict[uuid.UUID, dict[str, Any]] = {}
    for r in source_rows:
        src_meta[r.id] = {
            "source_name": r.source_name,
            "registry_health_status": r.source_health_status,
        }

    runs = scr_repo.list_source_check_runs_for_org(
        session,
        org_id=org_id,
        org_type=org_type,
        limit=lim,
    )

    latest: dict[uuid.UUID, tuple[Any, dict[str, Any]]] = {}
    for run in runs:
        rs_raw = run.result_summary_json
        if not _is_connector_result_summary(rs_raw):
            continue
        rs = rs_raw if isinstance(rs_raw, dict) else {}
        sid = run.source_registry_id
        if sid in latest:
            continue
        latest[sid] = (run, rs)

    warning_counter: dict[str, int] = {}
    ch_counts: dict[str, int] = dict.fromkeys(_CONNECTOR_HEALTH_BUCKETS, 0)
    empty_connector_signals = 0
    dup_heavy = 0
    rr_heavy = 0
    flat_escalations: list[dict[str, Any]] = []

    rows_out: list[dict[str, Any]] = []

    for sid, (run, rs) in latest.items():
        meta = src_meta.get(sid, {})
        name = meta.get("source_name")
        reg_h_raw = meta.get("registry_health_status")
        reg_h = (
            str(reg_h_raw).strip()
            if reg_h_raw is not None and str(reg_h_raw).strip()
            else None
        )

        hc_raw = str(rs.get("health_status") or "").strip() or "unknown"
        hc = hc_raw if hc_raw in ch_counts else "unknown"
        ch_counts[hc] += 1

        wc_list = (
            rs.get("warning_codes") if isinstance(rs.get("warning_codes"), list) else []
        )
        wc_norm = [str(x) for x in wc_list]
        wc_set = set(wc_norm)
        if hc_raw == "empty" or "connector_run_empty" in wc_set:
            empty_connector_signals += 1

        for w in wc_norm:
            warning_counter[w] = warning_counter.get(w, 0) + 1

        cnt = rs.get("counts") if isinstance(rs.get("counts"), dict) else {}
        acc = int(cnt.get("accepted_count") or 0)
        dup = int(cnt.get("duplicate_count") or 0)
        rej = int(cnt.get("rejected_count") or 0)
        err = int(cnt.get("error_count") or 0)
        rr = int(cnt.get("review_required_count") or 0)
        tot = acc + dup + rej + err
        is_dup_heavy = tot >= 4 and dup >= max(3, int(0.35 * tot))
        is_rr_heavy = rr >= 4 or (tot >= 4 and rr >= max(2, int(0.28 * tot)))
        if is_dup_heavy:
            dup_heavy += 1
        if is_rr_heavy:
            rr_heavy += 1

        tags = _pressure_tags(
            rs,
            reg_h,
            duplicate_heavy=is_dup_heavy,
            review_heavy=is_rr_heavy,
        )

        esc_raw = rs.get("operator_escalation_recommendations")
        esc_list = esc_raw if isinstance(esc_raw, list) else []

        for e in esc_list:
            if isinstance(e, dict):
                row_e = dict(e)
                row_e.setdefault("source_registry_id", str(sid))
                row_e.setdefault("source_check_run_id", str(run.id))
                flat_escalations.append(row_e)

        intake_raw = rs.get("intake_run_id")
        intake_s = str(intake_raw) if intake_raw else None

        diag = str(rs.get("operator_diagnostic_message") or "").strip()
        mcounts = _manifest_counts_from_rs(rs)

        rows_out.append(
            {
                "source_registry_id": str(sid),
                "source_name": name,
                "registry_health_status": reg_h,
                "connector_health_status": hc_raw,
                "source_check_run_id": str(run.id),
                "check_status": run.check_status,
                "run_completed_at": _dt_iso(run.completed_at),
                "run_started_at": _dt_iso(run.started_at),
                "intake_run_id": intake_s,
                "warning_codes": wc_norm,
                "manifest_counts": mcounts,
                "intake_counts": cnt,
                "operator_diagnostic_message": diag or None,
                "operator_escalation_recommendations": esc_list,
                "pressure_category_tags": tags,
                "attention_summary": _attention_line(rs, reg_h, diag, esc_list),
            }
        )

    warning_ranked = [
        {"warning_code": k, "occurrences": v}
        for k, v in sorted(warning_counter.items(), key=lambda kv: (-kv[1], kv[0]))
    ][:48]

    rank_order = {
        "failed": 0,
        "empty": 1,
        "degraded": 2,
        "stale": 3,
        "healthy": 5,
        "unknown": 4,
    }

    rows_out.sort(
        key=lambda row: (
            rank_order.get(str(row.get("connector_health_status") or ""), 9),
            str(row.get("source_name") or ""),
        )
    )

    reg = _registry_health_rollups(source_rows)

    return {
        "schema_version": WORKBENCH_CONNECTOR_INTEL_SCHEMA_VERSION,
        "generated_at": now.isoformat(),
        "rollup": {
            "registry_health_counts": reg,
            "connector_health_counts": ch_counts,
            "sources_with_connector_summaries": len(latest),
            "empty_connector_runs": empty_connector_signals,
            "duplicate_heavy_sources": dup_heavy,
            "review_required_heavy_sources": rr_heavy,
            "operator_escalation_rows_total": len(flat_escalations),
            "warning_codes_ranked": warning_ranked,
            "registry_sources_degraded": reg.get(SourceHealthStatus.degraded.value, 0),
            "registry_sources_failing": reg.get(SourceHealthStatus.failing.value, 0),
            "registry_sources_stale": reg.get(SourceHealthStatus.stale.value, 0),
        },
        "operator_escalation_recommendations_flat": flat_escalations[:80],
        "per_source_latest_connector_run": rows_out,
    }


_SEVERITY_RANK: dict[str, int] = {
    OperatorDecisionSeverity.critical.value: 5,
    OperatorDecisionSeverity.high.value: 4,
    OperatorDecisionSeverity.medium.value: 3,
    OperatorDecisionSeverity.low.value: 2,
    OperatorDecisionSeverity.info.value: 1,
}

_PRIORITY_RANK: dict[str, int] = {
    SourcePriorityLevel.critical.value: 4,
    SourcePriorityLevel.high.value: 3,
    SourcePriorityLevel.medium.value: 2,
    SourcePriorityLevel.low.value: 1,
}

_STRUCTURE_GAP_TYPES = frozenset(
    {
        CoverageGapType.missing_source_type.value,
        CoverageGapType.undercovered_domain.value,
        CoverageGapType.undercovered_applicant_type.value,
        CoverageGapType.undercovered_state.value,
        CoverageGapType.undercovered_region.value,
        CoverageGapType.undercovered_tribal_group.value,
    }
)

_DEGRADED_HEALTH = frozenset(
    {
        SourceHealthStatus.degraded.value,
        SourceHealthStatus.stale.value,
        SourceHealthStatus.attention_needed.value,
    }
)


def _review_item_severity(item: dict[str, Any]) -> str:
    rit = str(item.get("review_item_type") or "")
    qs = item.get("quality_score")
    dup = int(item.get("duplicate_risk_score") or 0)
    pri = int(item.get("priority") or 0)
    if rit == DiscoveryReviewItemType.duplicate_review.value and dup >= 48:
        return OperatorDecisionSeverity.high.value
    if qs is not None and int(qs) <= 50:
        return OperatorDecisionSeverity.high.value
    if qs is not None and int(qs) <= 62:
        return OperatorDecisionSeverity.medium.value
    if pri >= 70:
        return OperatorDecisionSeverity.high.value
    if pri >= 40:
        return OperatorDecisionSeverity.medium.value
    return OperatorDecisionSeverity.medium.value


def _review_item_action(item: dict[str, Any]) -> str:
    it = str(item.get("review_item_type") or "")
    if it == DiscoveryReviewItemType.source_verification.value:
        return OperatorDecisionAction.verify.value
    return OperatorDecisionAction.review.value


def _rec_decision_item_type(rec: dict[str, Any]) -> str:
    gt = str(rec.get("gap_type") or "")
    if gt == CoverageGapType.low_yield_source.value:
        return OperatorDecisionItemType.source_yield_issue.value
    if gt == CoverageGapType.unverified_priority_source.value:
        return OperatorDecisionItemType.source_verification.value
    if gt in _STRUCTURE_GAP_TYPES:
        return OperatorDecisionItemType.coverage_gap.value
    if rec.get("source_registry_id"):
        return OperatorDecisionItemType.source_recommendation.value
    return OperatorDecisionItemType.coverage_gap.value


def _severity_for_priority_level(pl: str | None) -> str:
    if pl == SourcePriorityLevel.critical.value:
        return OperatorDecisionSeverity.critical.value
    if pl == SourcePriorityLevel.high.value:
        return OperatorDecisionSeverity.high.value
    if pl == SourcePriorityLevel.medium.value:
        return OperatorDecisionSeverity.medium.value
    return OperatorDecisionSeverity.low.value


def _severity_for_degraded_health(h: str) -> str:
    if h == SourceHealthStatus.degraded.value:
        return OperatorDecisionSeverity.high.value
    if h == SourceHealthStatus.attention_needed.value:
        return OperatorDecisionSeverity.medium.value
    if h == SourceHealthStatus.stale.value:
        return OperatorDecisionSeverity.medium.value
    return OperatorDecisionSeverity.medium.value


def _intake_run_needs_attention(run: dict[str, Any]) -> bool:
    cc = int(run.get("candidate_count") or 0)
    rej = int(run.get("rejected_count") or 0)
    dup = int(run.get("duplicate_count") or 0)
    err = int(run.get("error_count") or 0)
    if err > 0:
        return True
    if rej + dup >= 5:
        return True
    if cc > 0 and (rej + dup) / cc >= 0.35:
        return True
    return False


def _sort_score(item: dict[str, Any]) -> tuple[int, int, str, str]:
    sev = str(item.get("severity") or OperatorDecisionSeverity.medium.value)
    sr = _SEVERITY_RANK.get(sev, 3)
    boost = int(item.get("priority_boost") or 0)
    return (-sr, -boost, str(item.get("item_type")), str(item.get("title")))


def _compute_decision_score(gap_intel: dict[str, Any]) -> int:
    scores = (
        int(gap_intel.get("coverage_score") or 0)
        + int(gap_intel.get("freshness_score") or 0)
        + int(gap_intel.get("reliability_score") or 0)
        + int(gap_intel.get("yield_score") or 0)
    )
    return max(0, min(100, int(round(scores / 4))))


def _matches_item_filters(
    item: dict[str, Any],
    *,
    severity: str | None,
    item_type: str | None,
    action: str | None,
    source_registry_id: uuid.UUID | None,
) -> bool:
    if severity is not None and item.get("severity") != severity:
        return False
    if item_type is not None and item.get("item_type") != item_type:
        return False
    if action is not None and item.get("recommended_action") != action:
        return False
    if source_registry_id is not None:
        refs = item.get("refs") or {}
        sid = refs.get("source_registry_id")
        if sid is None or str(sid) != str(source_registry_id):
            return False
    return True


def _strip_snapshots(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for it in items:
        c = copy.deepcopy(it)
        c.pop("source_snapshot", None)
        out.append(c)
    return out


def decision_pack_summary_compact(payload: dict[str, Any]) -> dict[str, Any]:
    """Export-friendly rollup (no large nested blobs)."""
    items = payload.get("decision_items") or []
    counts_by_type: dict[str, int] = {}
    counts_by_severity: dict[str, int] = {}
    for it in items:
        t = str(it.get("item_type") or "unknown")
        counts_by_type[t] = counts_by_type.get(t, 0) + 1
        s = str(it.get("severity") or "")
        if s:
            counts_by_severity[s] = counts_by_severity.get(s, 0) + 1
    return {
        "decision_pack_schema_version": payload.get("schema_version"),
        "generated_at": payload.get("generated_at"),
        "organization_id": payload.get("organization_id"),
        "is_demo": payload.get("is_demo"),
        "decision_score": payload.get("decision_score"),
        "decision_item_count": len(items),
        "counts_by_item_type": dict(sorted(counts_by_type.items())),
        "counts_by_severity": dict(sorted(counts_by_severity.items())),
        "priority_next_actions": payload.get("priority_next_actions"),
        "freshness_summary": payload.get("freshness_summary"),
    }


def export_priority_actions_sample(
    pack: dict[str, Any],
    *,
    cap: int = 50,
) -> list[dict[str, Any]]:
    """Ranked action-shaped rows for exports (capped)."""
    items = pack.get("decision_items") or []
    out: list[dict[str, Any]] = []
    for i, it in enumerate(items[: max(0, cap)]):
        out.append(
            {
                "rank": i + 1,
                "decision_id": it.get("decision_id"),
                "item_type": it.get("item_type"),
                "severity": it.get("severity"),
                "recommended_action": it.get("recommended_action"),
                "title": it.get("title"),
                "refs": it.get("refs"),
            }
        )
    return out


def operator_decision_pack_export_summary(pack: dict[str, Any]) -> dict[str, Any]:
    """Compact summary block for org snapshot exports."""
    summ = pack.get("summary") or {}
    return {
        "schema_version": pack.get("schema_version"),
        "generated_at": pack.get("generated_at"),
        "decision_score": pack.get("decision_score"),
        "rollup": {
            "open_review_items": summ.get("counts", {}).get("open_review_items"),
            "sources_due": summ.get("counts", {}).get("sources_due"),
            "sources_overdue": summ.get("counts", {}).get("sources_overdue"),
            "sources_failing": summ.get("counts", {}).get("sources_failing"),
            "decision_items_in_response": summ.get("decision_items_returned"),
        },
    }


def build_operator_actions_pack(
    session: Session,
    *,
    org_id: uuid.UUID,
    org_type: OrgType,
    now: datetime | None = None,
    intake_run_limit: int = 40,
    severity: str | None = None,
    item_type: str | None = None,
    action: str | None = None,
    source_registry_id: uuid.UUID | None = None,
    limit: int = 50,
    include_snapshots: bool = True,
) -> dict[str, Any]:
    """Ranked actions + minimal metadata (no discovery section blobs)."""
    full = build_operator_decision_pack(
        session,
        org_id=org_id,
        org_type=org_type,
        now=now,
        intake_run_limit=intake_run_limit,
        severity=severity,
        item_type=item_type,
        action=action,
        source_registry_id=source_registry_id,
        limit=limit,
        include_snapshots=include_snapshots,
    )
    return {
        "schema_version": full["schema_version"],
        "organization_id": full["organization_id"],
        "is_demo": full["is_demo"],
        "generated_at": full["generated_at"],
        "decision_score": full["decision_score"],
        "summary": full["summary"],
        "priority_next_actions": full["priority_next_actions"],
        "operator_actions": full["priority_next_actions"],
        "decision_items": full["decision_items"],
    }


def build_operator_decision_pack(
    session: Session,
    *,
    org_id: uuid.UUID,
    org_type: OrgType,
    now: datetime | None = None,
    intake_run_limit: int = 40,
    severity: str | None = None,
    item_type: str | None = None,
    action: str | None = None,
    source_registry_id: uuid.UUID | None = None,
    limit: int = 50,
    include_snapshots: bool = True,
) -> dict[str, Any]:
    """Single deterministic payload: operational signals + ranked decision_items."""
    ref_now = now or datetime.now(UTC)
    lim_cap = max(1, min(int(limit), 200))

    rows = ods.list_sources(session, org_id=org_id, org_type=org_type)

    freshness_summary = sfs.build_freshness_summary_payload(rows, now=ref_now)
    due_rows = sfs.filter_sources_due(rows, now=ref_now)
    overdue_rows = sfs.filter_sources_overdue(rows, now=ref_now)
    overdue_ids = {r.id for r in overdue_rows}

    due_only = [r for r in due_rows if r.id not in overdue_ids]

    gap_intel = dcg_svc.build_coverage_gap_intelligence(
        session,
        org_id=org_id,
        org_type=org_type,
        now=ref_now,
    )
    gap_compact = dcg_svc.coverage_gap_intel_summary_compact(gap_intel)
    decision_score = _compute_decision_score(gap_intel)

    open_reviews = d_review.list_review_items(
        session,
        org_id=org_id,
        org_type=org_type,
        open_queue_only=True,
        limit=500,
    )

    intake_lim = max(1, min(int(intake_run_limit), 200))
    intake_rows = intake_repo.list_discovery_intake_runs_for_org(
        session=session,
        org_id=org_id,
        org_type=org_type,
        limit=intake_lim,
    )
    recent_intake = [d_intake.intake_run_to_dict(r) for r in intake_rows]
    intake_attention = [r for r in recent_intake if _intake_run_needs_attention(r)]

    failing_sources = [
        r
        for r in rows
        if r.is_active
        and (r.source_health_status or "") == SourceHealthStatus.failing.value
    ]

    degraded_sources = [
        r
        for r in rows
        if r.is_active and (r.source_health_status or "") in _DEGRADED_HEALTH
    ]

    decision_items: list[dict[str, Any]] = []

    for item in open_reviews:
        itype = _review_queue_item_type(str(item.get("review_item_type") or ""))
        severity = _review_item_severity(item)
        decision_items.append(
            {
                "decision_id": _decision_id(
                    org_id,
                    "review",
                    str(item.get("id")),
                ),
                "item_type": itype,
                "severity": severity,
                "recommended_action": _review_item_action(item),
                "title": f"Discovery review: {item.get('review_item_type')}",
                "rationale": (
                    "Open discovery review queue item requires operator attention."
                ),
                "refs": {
                    "discovery_review_item_id": item.get("id"),
                    "grant_spark_id": item.get("grant_spark_id"),
                    "intake_candidate_id": item.get("intake_candidate_id"),
                    "intake_run_id": item.get("intake_run_id"),
                    "source_registry_id": item.get("source_registry_id"),
                },
                "priority_boost": min(100, int(item.get("priority") or 0)),
            }
        )

    for src in overdue_rows:
        pl = src.priority_level or SourcePriorityLevel.medium.value
        decision_items.append(
            {
                "decision_id": _decision_id(org_id, "overdue", str(src.id)),
                "item_type": OperatorDecisionItemType.source_overdue.value,
                "severity": _severity_for_priority_level(pl),
                "recommended_action": OperatorDecisionAction.check_source.value,
                "title": f"Overdue source check: {src.source_name}",
                "rationale": "Active source is past its next scheduled check window.",
                "refs": {"source_registry_id": str(src.id)},
                "priority_boost": _PRIORITY_RANK.get(pl, 2),
                "source_snapshot": {
                    "source_name": src.source_name,
                    "priority_level": pl,
                    "source_health_status": src.source_health_status,
                },
            }
        )

    for src in due_only:
        pl = src.priority_level or SourcePriorityLevel.medium.value
        decision_items.append(
            {
                "decision_id": _decision_id(org_id, "due", str(src.id)),
                "item_type": OperatorDecisionItemType.source_due.value,
                "severity": OperatorDecisionSeverity.low.value
                if pl == SourcePriorityLevel.low.value
                else OperatorDecisionSeverity.medium.value,
                "recommended_action": OperatorDecisionAction.check_source.value,
                "title": f"Due source check: {src.source_name}",
                "rationale": "Active source is due for a scheduled check.",
                "refs": {"source_registry_id": str(src.id)},
                "priority_boost": _PRIORITY_RANK.get(pl, 2),
                "source_snapshot": {
                    "source_name": src.source_name,
                    "priority_level": pl,
                    "source_health_status": src.source_health_status,
                },
            }
        )

    for src in failing_sources:
        pl = src.priority_level or SourcePriorityLevel.medium.value
        decision_items.append(
            {
                "decision_id": _decision_id(org_id, "failing", str(src.id)),
                "item_type": OperatorDecisionItemType.source_failing.value,
                "severity": OperatorDecisionSeverity.critical.value
                if pl == SourcePriorityLevel.critical.value
                else OperatorDecisionSeverity.high.value,
                "recommended_action": OperatorDecisionAction.resolve_failure.value,
                "title": f"Failing source health: {src.source_name}",
                "rationale": "Source health is failing based on recent check outcomes.",
                "refs": {"source_registry_id": str(src.id)},
                "priority_boost": _PRIORITY_RANK.get(pl, 2) + 2,
                "source_snapshot": {
                    "source_name": src.source_name,
                    "priority_level": pl,
                    "last_check_status": src.last_check_status,
                },
            }
        )

    for src in degraded_sources:
        pl = src.priority_level or SourcePriorityLevel.medium.value
        h = str(src.source_health_status or "")
        decision_items.append(
            {
                "decision_id": _decision_id(org_id, "degraded", str(src.id)),
                "item_type": OperatorDecisionItemType.source_recommendation.value,
                "severity": _severity_for_degraded_health(h),
                "recommended_action": (
                    OperatorDecisionAction.improve_source_quality.value
                ),
                "title": f"Degraded source health: {src.source_name}",
                "rationale": (
                    "Source health is degraded or stale; "
                    "review quality and check cadence."
                ),
                "refs": {"source_registry_id": str(src.id)},
                "priority_boost": _PRIORITY_RANK.get(pl, 2) + 1,
                "source_snapshot": {
                    "source_name": src.source_name,
                    "priority_level": pl,
                    "source_health_status": src.source_health_status,
                },
            }
        )

    for rec in gap_intel.get("source_recommendations") or []:
        sev = _severity_from_coverage(str(rec.get("severity") or "medium"))
        itype = _rec_decision_item_type(rec)
        action_raw = str(rec.get("action") or rec.get("operator_action") or "")
        decision_items.append(
            {
                "decision_id": _decision_id(
                    org_id,
                    "gap_rec",
                    str(rec.get("gap_id") or rec.get("recommendation_id")),
                ),
                "item_type": itype,
                "severity": sev,
                "recommended_action": _map_coverage_action_to_operator(action_raw),
                "title": str(rec.get("title") or "Coverage recommendation"),
                "rationale": str(rec.get("rationale") or ""),
                "refs": {
                    "gap_id": rec.get("gap_id"),
                    "recommendation_id": rec.get("recommendation_id"),
                    "source_registry_id": rec.get("source_registry_id"),
                    "gap_type": rec.get("gap_type"),
                },
                "priority_boost": _SEVERITY_RANK.get(sev, 3),
            }
        )

    for run in intake_attention:
        rid = str(run.get("id"))
        decision_items.append(
            {
                "decision_id": _decision_id(org_id, "intake", rid),
                "item_type": OperatorDecisionItemType.intake_run_attention.value,
                "severity": OperatorDecisionSeverity.medium.value,
                "recommended_action": OperatorDecisionAction.inspect_intake_run.value,
                "title": (
                    f"Intake run needs review (rejected/duplicate/errors): {rid[:8]}..."
                ),
                "rationale": (
                    "Intake run shows elevated rejected, duplicate, or error outcomes "
                    "relative to candidate volume."
                ),
                "refs": {
                    "intake_run_id": rid,
                    "source_registry_id": run.get("source_registry_id"),
                },
                "priority_boost": 2,
            }
        )

    decision_items.sort(key=_sort_score)
    total_before_filter = len(decision_items)

    filtered = [
        x
        for x in decision_items
        if _matches_item_filters(
            x,
            severity=severity,
            item_type=item_type,
            action=action,
            source_registry_id=source_registry_id,
        )
    ]
    trimmed = filtered[:lim_cap]

    if not include_snapshots:
        trimmed = _strip_snapshots(trimmed)

    priority_cap = min(50, lim_cap, len(trimmed))
    priority_next = [
        {
            "rank": i + 1,
            "decision_id": x["decision_id"],
            "item_type": x["item_type"],
            "severity": x["severity"],
            "recommended_action": x["recommended_action"],
            "title": x["title"],
        }
        for i, x in enumerate(trimmed[:priority_cap])
    ]

    is_demo = org_type == "demo"
    quality_sparks_candidates_refs = {
        "open_review_items_count": len(open_reviews),
        "note": (
            "Quality-risk signals for candidates and Sparks are represented via "
            "the discovery review queue (review_item / quality_risk rows)."
        ),
    }

    filters_echo = {
        "severity": severity,
        "item_type": item_type,
        "action": action,
        "source_registry_id": str(source_registry_id) if source_registry_id else None,
        "limit": lim_cap,
        "include_snapshots": include_snapshots,
        "intake_run_limit": intake_lim,
    }

    summary = {
        "decision_score": decision_score,
        "total_decision_items_before_filters": total_before_filter,
        "decision_items_after_filters": len(filtered),
        "decision_items_returned": len(trimmed),
        "filters_applied": filters_echo,
        "counts": {
            "open_review_items": len(open_reviews),
            "sources_due": len(due_only),
            "sources_overdue": len(overdue_rows),
            "sources_failing": len(failing_sources),
            "sources_degraded_attention": len(degraded_sources),
            "recent_intake_runs": len(recent_intake),
            "intake_runs_flagged": len(intake_attention),
        },
    }

    compact_export = decision_pack_summary_compact(
        {
            "schema_version": DECISION_PACK_SCHEMA_VERSION,
            "generated_at": ref_now.isoformat(),
            "organization_id": str(org_id),
            "is_demo": is_demo,
            "decision_score": decision_score,
            "decision_items": trimmed,
            "priority_next_actions": priority_next,
            "freshness_summary": freshness_summary,
        }
    )

    connector_intel = build_workbench_connector_intelligence(
        session,
        org_id=org_id,
        org_type=org_type,
        source_rows=rows,
        now=ref_now,
    )

    pack = {
        "schema_version": DECISION_PACK_SCHEMA_VERSION,
        "organization_id": str(org_id),
        "is_demo": is_demo,
        "generated_at": ref_now.isoformat(),
        "decision_score": decision_score,
        "summary": summary,
        "connector_intelligence": connector_intel,
        "freshness_summary": freshness_summary,
        "coverage_gap_summary": gap_compact,
        "open_review_items": open_reviews,
        "quality_risk_signals": quality_sparks_candidates_refs,
        "sources_due": [ods.opportunity_source_to_dict(r) for r in due_only],
        "sources_overdue": [ods.opportunity_source_to_dict(r) for r in overdue_rows],
        "sources_failing": [ods.opportunity_source_to_dict(r) for r in failing_sources],
        "coverage_gaps": gap_intel.get("coverage_gaps"),
        "source_recommendations": gap_intel.get("source_recommendations"),
        "operator_next_actions_from_coverage": gap_intel.get("operator_next_actions"),
        "recent_intake_runs": recent_intake,
        "intake_runs_flagged": intake_attention,
        "decision_items": trimmed,
        "priority_next_actions": priority_next,
        "decision_summary_export": compact_export,
        "operator_brief": compact_export,
    }
    from nativeforge.services import operator_action_service as oa_svc

    return oa_svc.enrich_decision_pack_with_ledger(
        session,
        org_id=org_id,
        org_type=org_type,
        pack=pack,
    )
