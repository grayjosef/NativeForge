"""Sprint 15: deterministic source scheduling, freshness, and check-run bookkeeping."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy.orm import Session

from nativeforge.db.models import (
    NfOpportunitySource,
    NfSourceCheckRun,
    Organization,
    is_demo_for_org_type,
)
from nativeforge.domain.enums import (
    AuditAction,
    SourceCheckRunStatus,
    SourceHealthStatus,
    SourceLastCheckStatus,
    SourcePriorityLevel,
)
from nativeforge.lib.demo_isolation import OrgType
from nativeforge.repositories import audit_events as audit_repo

FRESHNESS_DETAIL_SCHEMA_VERSION = "nf_source_freshness_detail_v1"
SUMMARY_SCHEMA_VERSION = "nf_source_freshness_summary_v1"
CHECK_RUN_SCHEMA_VERSION = "nf_source_check_run_v1"

_PRIORITY_DEFAULT_INTERVAL_DAYS: dict[str, int] = {
    SourcePriorityLevel.critical.value: 1,
    SourcePriorityLevel.high.value: 3,
    SourcePriorityLevel.medium.value: 7,
    SourcePriorityLevel.low.value: 14,
}

_INACTIVE_INTERVAL_FALLBACK = 30


def check_run_to_dict(row: NfSourceCheckRun) -> dict[str, Any]:
    def _dt(v: object | None) -> str | None:
        if v is None:
            return None
        if isinstance(v, datetime):
            return v.isoformat()
        return str(v)

    return {
        "schema_version": CHECK_RUN_SCHEMA_VERSION,
        "id": str(row.id),
        "organization_id": str(row.organization_id),
        "is_demo": row.is_demo,
        "source_registry_id": str(row.source_registry_id),
        "check_mode": row.check_mode,
        "check_status": row.check_status,
        "started_at": _dt(row.started_at),
        "completed_at": _dt(row.completed_at),
        "checked_for_period_start": _dt(row.checked_for_period_start),
        "checked_for_period_end": _dt(row.checked_for_period_end),
        "opportunities_seen_count": row.opportunities_seen_count,
        "new_candidates_count": row.new_candidates_count,
        "accepted_count": row.accepted_count,
        "duplicate_count": row.duplicate_count,
        "rejected_count": row.rejected_count,
        "review_items_created_count": row.review_items_created_count,
        "error_code": row.error_code,
        "error_message": row.error_message,
        "operator_notes": row.operator_notes,
        "result_summary_json": row.result_summary_json,
        "created_at": _dt(row.created_at),
        "updated_at": _dt(row.updated_at),
    }


def effective_check_interval_days(source: NfOpportunitySource) -> int:
    if source.check_interval_days is not None:
        return max(1, int(source.check_interval_days))
    if source.freshness_interval_days is not None:
        return max(1, int(source.freshness_interval_days))
    if not source.is_active:
        return _INACTIVE_INTERVAL_FALLBACK
    pl = source.priority_level
    return _PRIORITY_DEFAULT_INTERVAL_DAYS.get(pl, _INACTIVE_INTERVAL_FALLBACK)


def compute_next_check_due_at(
    *,
    last_checked_at: datetime | None,
    interval_days: int,
    reference_now: datetime,
) -> datetime:
    base = last_checked_at or reference_now
    if base.tzinfo is None:
        base = base.replace(tzinfo=UTC)
    return base + timedelta(days=max(1, interval_days))


def effective_next_deadline(
    source: NfOpportunitySource,
    *,
    now: datetime,
) -> datetime | None:
    if source.next_check_due_at is not None:
        v = source.next_check_due_at
        return v.replace(tzinfo=UTC) if v.tzinfo is None else v
    interval = effective_check_interval_days(source)
    base = source.last_checked_at or source.created_at
    if base is None:
        return None
    if base.tzinfo is None:
        base = base.replace(tzinfo=UTC)
    return base + timedelta(days=interval)


def is_active_source_due(
    source: NfOpportunitySource,
    *,
    now: datetime,
) -> bool:
    if not source.is_active:
        return False
    due = effective_next_deadline(source, now=now)
    if due is None:
        return True
    return due <= now


def is_active_source_overdue(
    source: NfOpportunitySource,
    *,
    now: datetime,
) -> bool:
    if not source.is_active:
        return False
    due = effective_next_deadline(source, now=now)
    if due is None:
        return False
    return due < now


def opportunity_source_freshness_detail(
    source: NfOpportunitySource,
    *,
    now: datetime,
) -> dict[str, Any]:
    interval = effective_check_interval_days(source)
    due_at = effective_next_deadline(source, now=now)
    due_flag = is_active_source_due(source, now=now)
    overdue_flag = is_active_source_overdue(source, now=now)
    return {
        "freshness_schema_version": FRESHNESS_DETAIL_SCHEMA_VERSION,
        "source_id": str(source.id),
        "source_name": source.source_name,
        "is_active": source.is_active,
        "effective_check_interval_days": interval,
        "next_check_due_at": due_at.isoformat() if due_at else None,
        "stored_next_check_due_at": source.next_check_due_at.isoformat()
        if source.next_check_due_at
        else None,
        "last_checked_at": source.last_checked_at.isoformat()
        if source.last_checked_at
        else None,
        "is_due_for_check": due_flag,
        "is_overdue": overdue_flag,
        "source_health_status": source.source_health_status,
        "last_check_status": source.last_check_status,
        "consecutive_failure_count": source.consecutive_failure_count,
        "consecutive_empty_check_count": source.consecutive_empty_check_count,
        "freshness_checked_at": source.freshness_checked_at.isoformat()
        if source.freshness_checked_at
        else None,
    }


def build_freshness_summary_payload(
    rows: list[NfOpportunitySource],
    *,
    now: datetime,
) -> dict[str, Any]:
    by_health: dict[str, int] = {}
    by_last_check_status: dict[str, int] = {}
    by_priority: dict[str, int] = {}
    due_n = 0
    overdue_n = 0
    active_n = 0
    for r in rows:
        if not r.is_active:
            continue
        active_n += 1
        h = r.source_health_status or SourceHealthStatus.unknown.value
        by_health[h] = by_health.get(h, 0) + 1
        lc = r.last_check_status or "unset"
        by_last_check_status[lc] = by_last_check_status.get(lc, 0) + 1
        by_priority[r.priority_level] = by_priority.get(r.priority_level, 0) + 1
        if is_active_source_due(r, now=now):
            due_n += 1
        if is_active_source_overdue(r, now=now):
            overdue_n += 1

    return {
        "summary_schema_version": SUMMARY_SCHEMA_VERSION,
        "generated_at": now.isoformat(),
        "active_source_count": active_n,
        "due_for_check_count": due_n,
        "overdue_count": overdue_n,
        "by_source_health_status": by_health,
        "by_last_check_status": by_last_check_status,
        "by_priority_level": by_priority,
    }


def map_run_status_to_last_check_status(run_status: str) -> str:
    try:
        st = SourceCheckRunStatus(run_status)
    except ValueError:
        return SourceLastCheckStatus.pending.value
    if st in (SourceCheckRunStatus.succeeded,):
        return SourceLastCheckStatus.success.value
    if st == SourceCheckRunStatus.succeeded_with_warnings:
        return SourceLastCheckStatus.partial.value
    if st == SourceCheckRunStatus.failed:
        return SourceLastCheckStatus.failed.value
    if st == SourceCheckRunStatus.canceled:
        return SourceLastCheckStatus.skipped.value
    return SourceLastCheckStatus.pending.value


def _derive_health_from_counters(
    *,
    check_status: str,
    failure_count: int,
    empty_count: int,
    now: datetime,
    next_due: datetime,
) -> str:
    try:
        st = SourceCheckRunStatus(check_status)
    except ValueError:
        return SourceHealthStatus.unknown.value

    if st == SourceCheckRunStatus.failed:
        if failure_count >= 3:
            return SourceHealthStatus.failing.value
        if failure_count >= 1:
            return SourceHealthStatus.degraded.value
        return SourceHealthStatus.attention_needed.value

    if st in (
        SourceCheckRunStatus.succeeded,
        SourceCheckRunStatus.succeeded_with_warnings,
    ):
        if empty_count >= 3:
            return SourceHealthStatus.degraded.value
        if next_due < now:
            return SourceHealthStatus.stale.value
        return SourceHealthStatus.healthy.value

    return SourceHealthStatus.unknown.value


def finalize_completed_source_check(
    session: Session,
    *,
    org: Organization,
    org_type: OrgType,
    run: NfSourceCheckRun,
    source: NfOpportunitySource,
    patch: dict[str, Any],
    now: datetime | None = None,
) -> tuple[NfSourceCheckRun, dict[str, Any]]:
    """Persist completed check run + refresh registry row + audits."""
    ref_now = now or datetime.now(UTC)
    was_overdue = is_active_source_overdue(source, now=ref_now)
    previous_health = source.source_health_status

    check_status = str(patch["check_status"])
    opportunities_seen = int(patch.get("opportunities_seen_count", 0))
    completed_at = ref_now

    try:
        st = SourceCheckRunStatus(check_status)
    except ValueError as e:
        raise ValueError("invalid check_status") from e

    run.opportunities_seen_count = int(patch.get("opportunities_seen_count", 0))
    run.new_candidates_count = int(patch.get("new_candidates_count", 0))
    run.accepted_count = int(patch.get("accepted_count", 0))
    run.duplicate_count = int(patch.get("duplicate_count", 0))
    run.rejected_count = int(patch.get("rejected_count", 0))
    run.review_items_created_count = int(patch.get("review_items_created_count", 0))
    run.error_code = patch.get("error_code")
    run.error_message = patch.get("error_message")
    if "operator_notes" in patch:
        run.operator_notes = patch.get("operator_notes")
    rs = patch.get("result_summary")
    if rs is not None:
        run.result_summary_json = rs
    run.check_status = check_status
    run.completed_at = completed_at
    session.flush()

    last_st = map_run_status_to_last_check_status(check_status)

    fail_ct = source.consecutive_failure_count
    empty_ct = source.consecutive_empty_check_count

    if st == SourceCheckRunStatus.failed:
        fail_ct += 1
    elif st in (
        SourceCheckRunStatus.succeeded,
        SourceCheckRunStatus.succeeded_with_warnings,
    ):
        fail_ct = 0

    if st in (
        SourceCheckRunStatus.succeeded,
        SourceCheckRunStatus.succeeded_with_warnings,
    ):
        if opportunities_seen == 0:
            empty_ct += 1
        else:
            empty_ct = 0

    interval = effective_check_interval_days(source)
    next_due = compute_next_check_due_at(
        last_checked_at=completed_at,
        interval_days=interval,
        reference_now=ref_now,
    )

    source.last_checked_at = completed_at
    if st in (
        SourceCheckRunStatus.succeeded,
        SourceCheckRunStatus.succeeded_with_warnings,
    ):
        source.last_successful_check_at = completed_at
    if st == SourceCheckRunStatus.failed:
        source.last_error = str(
            patch.get("error_message") or patch.get("error_code") or "check_failed"
        )
    source.last_check_status = last_st
    source.last_check_run_id = run.id
    source.last_check_summary_json = {
        "check_run_id": str(run.id),
        "check_status": check_status,
        "opportunities_seen_count": run.opportunities_seen_count,
        "new_candidates_count": run.new_candidates_count,
        "result_summary": run.result_summary_json,
    }
    source.next_check_due_at = next_due
    source.consecutive_failure_count = fail_ct
    source.consecutive_empty_check_count = empty_ct
    source.freshness_checked_at = ref_now

    health = _derive_health_from_counters(
        check_status=check_status,
        failure_count=fail_ct,
        empty_count=empty_ct,
        now=ref_now,
        next_due=next_due,
    )
    source.source_health_status = health

    is_demo = is_demo_for_org_type(org.org_type)

    audit_repo.append_org_audit_event(
        session,
        organization_id=org.id,
        is_demo=is_demo,
        action=AuditAction.source_check_run_completed,
        payload={
            "source_check_run_id": str(run.id),
            "source_registry_id": str(source.id),
            "check_status": check_status,
            "source_health_status": health,
        },
        actor_id=None,
    )

    audit_repo.append_org_audit_event(
        session,
        organization_id=org.id,
        is_demo=is_demo,
        action=AuditAction.source_freshness_evaluated,
        payload={
            "source_registry_id": str(source.id),
            "next_check_due_at": next_due.isoformat(),
            "source_health_status": health,
        },
        actor_id=None,
    )

    extra: dict[str, Any] = {}
    if was_overdue:
        audit_repo.append_org_audit_event(
            session,
            organization_id=org.id,
            is_demo=is_demo,
            action=AuditAction.source_marked_overdue,
            payload={
                "source_registry_id": str(source.id),
                "resolved_check_run_id": str(run.id),
                "previous_health": previous_health,
            },
            actor_id=None,
        )
        extra["marked_overdue_audit"] = True

    session.flush()
    return run, extra


def filter_sources_due(
    rows: list[NfOpportunitySource],
    *,
    now: datetime,
) -> list[NfOpportunitySource]:
    return [r for r in rows if is_active_source_due(r, now=now)]


def filter_sources_overdue(
    rows: list[NfOpportunitySource],
    *,
    now: datetime,
) -> list[NfOpportunitySource]:
    return [r for r in rows if is_active_source_overdue(r, now=now)]
