"""Sprint 5: grant pursuit pipeline — create from scored spark, tasks, calendar."""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime
from typing import Any

from sqlalchemy.orm import Session

from nativeforge.db.models import (
    NfGrantPursuit,
    NfGrantSpark,
    NfPursuitCalendarEvent,
    NfPursuitTask,
    Organization,
    is_demo_for_org_type,
)
from nativeforge.domain.enums import (
    AuditAction,
    GrantPipelineStage,
    PursuitCalendarKind,
    PursuitTaskStatus,
    PursuitWorkflowStatus,
)
from nativeforge.lib.demo_isolation import OrgType
from nativeforge.repositories import grant_sparks as gs_repo
from nativeforge.repositories import nofo_extraction as ne_repo
from nativeforge.repositories import pursuits as pursuit_repo
from nativeforge.repositories import spark_scores as score_repo


class GrantSparkNotFoundError(Exception):
    """Scoped spark missing."""


class SparkNotScoredError(Exception):
    """At least one spark score is required to open a pursuit."""


class PursuitAlreadyExistsError(Exception):
    """Only one pursuit row per Grant Spark."""


class PursuitNotFoundError(Exception):
    """Scoped pursuit missing."""


class PursuitTaskNotFoundError(Exception):
    """Scoped task missing."""


_DEFAULT_TASKS: tuple[tuple[str, int], ...] = (
    ("Review NOFO checklist against tribal capacity", 0),
    ("Gather required attachments and certifications", 1),
    ("Schedule internal draft review before submission", 2),
)


def _dt(v: object | None) -> str | None:
    if v is None:
        return None
    if isinstance(v, datetime):
        return v.isoformat()
    if isinstance(v, date):
        return v.isoformat()
    return str(v)


def pursuit_to_dict(
    row: NfGrantPursuit,
    *,
    spark_title: str | None = None,
) -> dict[str, Any]:
    return {
        "id": str(row.id),
        "organization_id": str(row.organization_id),
        "grant_spark_id": str(row.grant_spark_id),
        "spark_score_id": str(row.spark_score_id) if row.spark_score_id else None,
        "status": row.status,
        "notes": row.notes,
        "spark_title": spark_title,
        "created_at": _dt(row.created_at),
        "updated_at": _dt(row.updated_at),
    }


def task_to_dict(row: NfPursuitTask) -> dict[str, Any]:
    return {
        "id": str(row.id),
        "grant_pursuit_id": str(row.grant_pursuit_id),
        "title": row.title,
        "description": row.description,
        "status": row.status,
        "sort_order": row.sort_order,
        "due_at": _dt(row.due_at),
        "completed_at": _dt(row.completed_at),
        "spark_requirement_id": str(row.spark_requirement_id)
        if row.spark_requirement_id
        else None,
        "created_at": _dt(row.created_at),
        "updated_at": _dt(row.updated_at),
    }


def calendar_event_to_dict(row: NfPursuitCalendarEvent) -> dict[str, Any]:
    return {
        "id": str(row.id),
        "grant_pursuit_id": str(row.grant_pursuit_id),
        "kind": row.kind,
        "title": row.title,
        "occurs_at": _dt(row.occurs_at),
        "notes": row.notes,
        "pursuit_task_id": str(row.pursuit_task_id) if row.pursuit_task_id else None,
        "created_at": _dt(row.created_at),
        "updated_at": _dt(row.updated_at),
    }


def _seed_deadline_events(
    session: Session,
    *,
    pursuit: NfGrantPursuit,
    spark: NfGrantSpark,
    is_demo: bool,
) -> None:
    if spark.loi_deadline is not None:
        title = spark.opportunity_title
        short = title if len(title) <= 200 else title[:197] + "..."
        session.add(
            NfPursuitCalendarEvent(
                id=uuid.uuid4(),
                organization_id=pursuit.organization_id,
                grant_pursuit_id=pursuit.id,
                is_demo=is_demo,
                kind=PursuitCalendarKind.loi_deadline.value,
                title=f"Letter of intent deadline — {short}",
                occurs_at=spark.loi_deadline,
                notes=None,
                pursuit_task_id=None,
            )
        )
    if spark.application_deadline is not None:
        title = spark.opportunity_title
        short = title if len(title) <= 200 else title[:197] + "..."
        session.add(
            NfPursuitCalendarEvent(
                id=uuid.uuid4(),
                organization_id=pursuit.organization_id,
                grant_pursuit_id=pursuit.id,
                is_demo=is_demo,
                kind=PursuitCalendarKind.application_deadline.value,
                title=f"Application deadline — {short}",
                occurs_at=spark.application_deadline,
                notes=None,
                pursuit_task_id=None,
            )
        )


def _seed_tasks(
    session: Session,
    *,
    pursuit: NfGrantPursuit,
    spark: NfGrantSpark,
    org_type: OrgType,
    is_demo: bool,
) -> None:
    run = ne_repo.get_latest_extraction_run(
        session=session,
        spark_id=spark.id,
        org_id=pursuit.organization_id,
        org_type=org_type,
    )
    rows = []
    if run is not None:
        rows = ne_repo.list_requirements_for_run(
            session=session,
            extraction_run_id=run.id,
            org_id=pursuit.organization_id,
            org_type=org_type,
        )
    if rows:
        for i, req in enumerate(rows):
            session.add(
                NfPursuitTask(
                    id=uuid.uuid4(),
                    organization_id=pursuit.organization_id,
                    grant_pursuit_id=pursuit.id,
                    is_demo=is_demo,
                    title=req.label[:512],
                    description=req.description,
                    status=PursuitTaskStatus.pending.value,
                    sort_order=int(req.sort_order) if req.sort_order is not None else i,
                    due_at=None,
                    completed_at=None,
                    spark_requirement_id=req.id,
                )
            )
    else:
        for title, order in _DEFAULT_TASKS:
            session.add(
                NfPursuitTask(
                    id=uuid.uuid4(),
                    organization_id=pursuit.organization_id,
                    grant_pursuit_id=pursuit.id,
                    is_demo=is_demo,
                    title=title,
                    description=None,
                    status=PursuitTaskStatus.pending.value,
                    sort_order=order,
                    due_at=None,
                    completed_at=None,
                    spark_requirement_id=None,
                )
            )


def create_pursuit_from_spark(
    session: Session,
    *,
    org: Organization,
    org_type: OrgType,
    spark_id: uuid.UUID,
    actor_id: uuid.UUID | None,
    notes: str | None = None,
) -> NfGrantPursuit:
    spark = gs_repo.get_grant_spark_scoped(
        session=session,
        spark_id=spark_id,
        org_id=org.id,
        org_type=org_type,
    )
    if spark is None:
        raise GrantSparkNotFoundError("grant spark not found")

    score = score_repo.get_latest_spark_score(
        session=session,
        spark_id=spark_id,
        org_id=org.id,
        org_type=org_type,
    )
    if score is None:
        raise SparkNotScoredError("Score this Grant Spark before opening a pursuit.")

    existing = pursuit_repo.get_grant_pursuit_by_spark(
        session=session,
        spark_id=spark_id,
        org_id=org.id,
        org_type=org_type,
    )
    if existing is not None:
        raise PursuitAlreadyExistsError("A pursuit already exists for this spark.")

    is_demo = is_demo_for_org_type(org.org_type)
    pursuit = NfGrantPursuit(
        id=uuid.uuid4(),
        organization_id=org.id,
        grant_spark_id=spark.id,
        spark_score_id=score.id,
        is_demo=is_demo,
        status=PursuitWorkflowStatus.active.value,
        notes=notes,
    )
    session.add(pursuit)
    session.flush()

    spark.pipeline_stage = GrantPipelineStage.pursuing.value

    _seed_deadline_events(
        session,
        pursuit=pursuit,
        spark=spark,
        is_demo=is_demo,
    )
    _seed_tasks(
        session,
        pursuit=pursuit,
        spark=spark,
        org_type=org_type,
        is_demo=is_demo,
    )
    session.flush()

    pursuit_repo.append_pursuit_audit(
        session,
        organization_id=org.id,
        is_demo=is_demo,
        action=AuditAction.grant_pursuit_created,
        payload={
            "grant_pursuit_id": str(pursuit.id),
            "grant_spark_id": str(spark.id),
            "spark_score_id": str(score.id),
        },
        actor_id=actor_id,
    )
    session.flush()
    return pursuit


def list_pursuits(
    session: Session,
    *,
    org_id: uuid.UUID,
    org_type: OrgType,
) -> list[dict[str, Any]]:
    rows = pursuit_repo.list_grant_pursuits(
        session=session,
        org_id=org_id,
        org_type=org_type,
    )
    out: list[dict[str, Any]] = []
    for p in rows:
        spark = session.get(NfGrantSpark, p.grant_spark_id)
        title = spark.opportunity_title if spark else None
        out.append(pursuit_to_dict(p, spark_title=title))
    return out


def get_pursuit_detail(
    session: Session,
    *,
    org_id: uuid.UUID,
    org_type: OrgType,
    pursuit_id: uuid.UUID,
) -> dict[str, Any]:
    p = pursuit_repo.get_grant_pursuit_scoped(
        session=session,
        pursuit_id=pursuit_id,
        org_id=org_id,
        org_type=org_type,
    )
    if p is None:
        raise PursuitNotFoundError("pursuit not found")
    spark = session.get(NfGrantSpark, p.grant_spark_id)
    title = spark.opportunity_title if spark else None
    tasks = pursuit_repo.list_tasks_for_pursuit(
        session=session,
        pursuit_id=p.id,
        org_id=org_id,
        org_type=org_type,
    )
    events = pursuit_repo.list_calendar_for_pursuit(
        session=session,
        pursuit_id=p.id,
        org_id=org_id,
        org_type=org_type,
    )
    return {
        "pursuit": pursuit_to_dict(p, spark_title=title),
        "tasks": [task_to_dict(t) for t in tasks],
        "calendar_events": [calendar_event_to_dict(e) for e in events],
    }


def update_pursuit(
    session: Session,
    *,
    org: Organization,
    org_type: OrgType,
    pursuit_id: uuid.UUID,
    patch: dict[str, Any],
    actor_id: uuid.UUID | None,
) -> NfGrantPursuit:
    p = pursuit_repo.get_grant_pursuit_scoped(
        session=session,
        pursuit_id=pursuit_id,
        org_id=org.id,
        org_type=org_type,
    )
    if p is None:
        raise PursuitNotFoundError("pursuit not found")
    before = {"status": p.status, "notes": p.notes}
    if "status" in patch:
        p.status = patch["status"]
    if "notes" in patch:
        p.notes = patch["notes"]
    session.flush()
    after = {"status": p.status, "notes": p.notes}
    if before != after:
        is_demo = is_demo_for_org_type(org.org_type)
        pursuit_repo.append_pursuit_audit(
            session,
            organization_id=org.id,
            is_demo=is_demo,
            action=AuditAction.grant_pursuit_updated,
            payload={
                "grant_pursuit_id": str(p.id),
                "before": before,
                "after": after,
            },
            actor_id=actor_id,
        )
        session.flush()
    return p


def create_task(
    session: Session,
    *,
    org: Organization,
    org_type: OrgType,
    pursuit_id: uuid.UUID,
    title: str,
    description: str | None,
    due_at: datetime | None,
    actor_id: uuid.UUID | None,
) -> NfPursuitTask:
    p = pursuit_repo.get_grant_pursuit_scoped(
        session=session,
        pursuit_id=pursuit_id,
        org_id=org.id,
        org_type=org_type,
    )
    if p is None:
        raise PursuitNotFoundError("pursuit not found")
    existing = pursuit_repo.list_tasks_for_pursuit(
        session=session,
        pursuit_id=pursuit_id,
        org_id=org.id,
        org_type=org_type,
    )
    next_order = max((t.sort_order for t in existing), default=-1) + 1
    is_demo = is_demo_for_org_type(org.org_type)
    row = NfPursuitTask(
        id=uuid.uuid4(),
        organization_id=org.id,
        grant_pursuit_id=pursuit_id,
        is_demo=is_demo,
        title=title,
        description=description,
        status=PursuitTaskStatus.pending.value,
        sort_order=next_order,
        due_at=due_at,
        completed_at=None,
        spark_requirement_id=None,
    )
    session.add(row)
    session.flush()
    pursuit_repo.append_pursuit_audit(
        session,
        organization_id=org.id,
        is_demo=is_demo,
        action=AuditAction.pursuit_task_created,
        payload={
            "grant_pursuit_id": str(pursuit_id),
            "pursuit_task_id": str(row.id),
            "title": title,
        },
        actor_id=actor_id,
    )
    session.flush()
    return row


def update_task(
    session: Session,
    *,
    org: Organization,
    org_type: OrgType,
    pursuit_id: uuid.UUID,
    task_id: uuid.UUID,
    patch: dict[str, Any],
    actor_id: uuid.UUID | None,
) -> NfPursuitTask:
    t = pursuit_repo.get_task_scoped(
        session=session,
        pursuit_id=pursuit_id,
        task_id=task_id,
        org_id=org.id,
        org_type=org_type,
    )
    if t is None:
        raise PursuitTaskNotFoundError("task not found")
    before = {
        "title": t.title,
        "description": t.description,
        "status": t.status,
        "due_at": _dt(t.due_at),
        "completed_at": _dt(t.completed_at),
    }
    if "title" in patch:
        t.title = patch["title"]
    if "description" in patch:
        t.description = patch["description"]
    if "status" in patch:
        t.status = patch["status"]
        if t.status == PursuitTaskStatus.done.value:
            if t.completed_at is None:
                t.completed_at = datetime.now(UTC)
        elif t.completed_at is not None:
            t.completed_at = None
    if "due_at" in patch:
        t.due_at = patch["due_at"]
    session.flush()
    after = {
        "title": t.title,
        "description": t.description,
        "status": t.status,
        "due_at": _dt(t.due_at),
        "completed_at": _dt(t.completed_at),
    }
    if before != after:
        is_demo = is_demo_for_org_type(org.org_type)
        pursuit_repo.append_pursuit_audit(
            session,
            organization_id=org.id,
            is_demo=is_demo,
            action=AuditAction.pursuit_task_updated,
            payload={
                "grant_pursuit_id": str(pursuit_id),
                "pursuit_task_id": str(task_id),
                "before": before,
                "after": after,
            },
            actor_id=actor_id,
        )
        session.flush()
    return t


def create_calendar_event(
    session: Session,
    *,
    org: Organization,
    org_type: OrgType,
    pursuit_id: uuid.UUID,
    kind: str,
    title: str,
    occurs_at: datetime,
    notes: str | None,
    pursuit_task_id: uuid.UUID | None,
    actor_id: uuid.UUID | None,
) -> NfPursuitCalendarEvent:
    p = pursuit_repo.get_grant_pursuit_scoped(
        session=session,
        pursuit_id=pursuit_id,
        org_id=org.id,
        org_type=org_type,
    )
    if p is None:
        raise PursuitNotFoundError("pursuit not found")
    if pursuit_task_id is not None:
        task = pursuit_repo.get_task_scoped(
            session=session,
            pursuit_id=pursuit_id,
            task_id=pursuit_task_id,
            org_id=org.id,
            org_type=org_type,
        )
        if task is None:
            raise PursuitTaskNotFoundError("task not found")
    is_demo = is_demo_for_org_type(org.org_type)
    row = NfPursuitCalendarEvent(
        id=uuid.uuid4(),
        organization_id=org.id,
        grant_pursuit_id=pursuit_id,
        is_demo=is_demo,
        kind=kind,
        title=title,
        occurs_at=occurs_at,
        notes=notes,
        pursuit_task_id=pursuit_task_id,
    )
    session.add(row)
    session.flush()
    pursuit_repo.append_pursuit_audit(
        session,
        organization_id=org.id,
        is_demo=is_demo,
        action=AuditAction.pursuit_calendar_event_created,
        payload={
            "grant_pursuit_id": str(pursuit_id),
            "calendar_event_id": str(row.id),
            "kind": kind,
        },
        actor_id=actor_id,
    )
    session.flush()
    return row


def list_org_calendar(
    session: Session,
    *,
    org_id: uuid.UUID,
    org_type: OrgType,
    start_at: datetime,
    end_at: datetime,
) -> list[dict[str, Any]]:
    rows = pursuit_repo.list_calendar_for_org_window(
        session=session,
        org_id=org_id,
        org_type=org_type,
        start_at=start_at,
        end_at=end_at,
    )
    return [calendar_event_to_dict(r) for r in rows]
