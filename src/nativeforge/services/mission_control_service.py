"""Organization-wide work intelligence from canonical pursuit records.

Mission Control does not store a second task list. It reads pursuits, tasks,
deadlines, funder interactions, packages and review artifacts, then ranks
what already exists. Workspace and the individual command center share
`build_pursuit_stages`.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from nativeforge.db.models import (
    NfFormPackage,
    NfGrantPursuit,
    NfGrantSpark,
    NfPursuitBrief,
    NfPursuitCalendarEvent,
    NfPursuitTask,
    NfReviewArtifact,
    NfSparkRequirement,
    NfSparkScore,
    NfTribalProfile,
)
from nativeforge.services import funder_interaction_service as interactions
from nativeforge.services.dev_org_membership_bootstrap_service import MEMBERSHIPS
from nativeforge.services.pursuit_command_center_service import (
    _iso,
    _next_action,
    build_pursuit_stages,
    extract_engagement_facts,
)

SCHEMA_VERSION = "nf_mission_control_v1"
STALE_AFTER = timedelta(days=14)
DUE_SOON = timedelta(days=7)
DUE_WEEK = timedelta(days=7)
DUE_MONTH = timedelta(days=30)

_ATTENTION_ORDER = (
    "blocked",
    "overdue",
    "due_soon",
    "needs_review",
    "waiting",
    "in_progress",
    "ready",
)


def _aware(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value


def _days(when: datetime | None, *, now: datetime) -> int | None:
    instant = _aware(when)
    if instant is None:
        return None
    return int((instant - now).total_seconds() // 86400)


def _bucket(when: datetime | None, *, now: datetime) -> str | None:
    instant = _aware(when)
    if instant is None:
        return None
    delta = instant.date() - now.date()
    days = delta.days
    if days < 0:
        return "overdue"
    if days == 0:
        return "today"
    if days <= 7:
        return "next_7_days"
    if days <= 30:
        return "next_30_days"
    return "later"


def membership_belongs_to_org(
    *,
    connection: Any,
    organization_id: uuid.UUID,
    membership_id: uuid.UUID,
) -> bool:
    row = connection.execute(
        select(MEMBERSHIPS.c.id).where(
            MEMBERSHIPS.c.id == membership_id,
            MEMBERSHIPS.c.organization_id == organization_id,
            MEMBERSHIPS.c.state == "active",
            MEMBERSHIPS.c.revoked_at.is_(None),
        )
    ).first()
    return row is not None


def membership_id_for_identity(
    *,
    connection: Any,
    organization_id: uuid.UUID,
    identity_id: uuid.UUID | str | None,
) -> uuid.UUID | None:
    if not identity_id:
        return None
    try:
        ident = uuid.UUID(str(identity_id))
    except (ValueError, TypeError):
        return None
    row = connection.execute(
        select(MEMBERSHIPS.c.id).where(
            MEMBERSHIPS.c.organization_id == organization_id,
            MEMBERSHIPS.c.identity_id == ident,
            MEMBERSHIPS.c.state == "active",
            MEMBERSHIPS.c.revoked_at.is_(None),
        )
    ).first()
    return row[0] if row else None


def assemble_mission_control(
    *,
    session: Session,
    organization_id: uuid.UUID | str,
    viewer_membership_id: uuid.UUID | None = None,
) -> dict[str, Any]:
    org = uuid.UUID(str(organization_id))
    now = datetime.now(tz=UTC)

    sparks = list(
        session.scalars(select(NfGrantSpark).where(NfGrantSpark.organization_id == org))
    )
    pursuits = list(
        session.scalars(
            select(NfGrantPursuit).where(NfGrantPursuit.organization_id == org)
        )
    )
    tasks = list(
        session.scalars(
            select(NfPursuitTask)
            .where(NfPursuitTask.organization_id == org)
            .order_by(NfPursuitTask.sort_order, NfPursuitTask.created_at)
        )
    )
    calendar = list(
        session.scalars(
            select(NfPursuitCalendarEvent)
            .where(NfPursuitCalendarEvent.organization_id == org)
            .order_by(NfPursuitCalendarEvent.occurs_at)
        )
    )
    scores = list(
        session.scalars(
            select(NfSparkScore)
            .where(NfSparkScore.organization_id == org)
            .order_by(NfSparkScore.created_at.desc())
        )
    )
    packages = list(
        session.scalars(
            select(NfFormPackage).where(NfFormPackage.organization_id == org)
        )
    )
    artifacts = list(
        session.scalars(
            select(NfReviewArtifact).where(NfReviewArtifact.organization_id == org)
        )
    )
    briefs = list(
        session.scalars(
            select(NfPursuitBrief).where(NfPursuitBrief.organization_id == org)
        )
    )
    req_rows = list(
        session.execute(
            select(
                NfSparkRequirement.grant_spark_id,
                func.count().label("n"),
            )
            .where(NfSparkRequirement.organization_id == org)
            .group_by(NfSparkRequirement.grant_spark_id)
        )
    )
    has_profile = bool(
        session.scalar(
            select(func.count())
            .select_from(NfTribalProfile)
            .where(NfTribalProfile.organization_id == org)
        )
    )
    recorded = interactions.list_interactions(
        connection=session.connection(),
        organization_id=org,
    )

    spark_by_id = {s.id: s for s in sparks}
    tasks_by_pursuit: dict[uuid.UUID, list[NfPursuitTask]] = {}
    for task in tasks:
        tasks_by_pursuit.setdefault(task.grant_pursuit_id, []).append(task)
    cal_by_pursuit: dict[uuid.UUID, list[NfPursuitCalendarEvent]] = {}
    for event in calendar:
        cal_by_pursuit.setdefault(event.grant_pursuit_id, []).append(event)
    score_by_spark: dict[uuid.UUID, NfSparkScore] = {}
    for score in scores:
        score_by_spark.setdefault(score.grant_spark_id, score)
    pkg_by_pursuit = {p.grant_pursuit_id: p for p in packages}
    art_by_id = {a.id: a for a in artifacts}
    req_count = {row[0]: int(row[1]) for row in req_rows}
    ixn_by_spark: dict[uuid.UUID, list[dict[str, Any]]] = {}
    for row in recorded:
        sid = uuid.UUID(str(row["grant_spark_id"]))
        ixn_by_spark.setdefault(sid, []).append(row)

    work: list[dict[str, Any]] = []
    active_cards: list[dict[str, Any]] = []
    recently: list[dict[str, Any]] = []
    deadline_items: list[dict[str, Any]] = []

    for pursuit in pursuits:
        spark = spark_by_id.get(pursuit.grant_spark_id)
        if spark is None:
            continue
        p_tasks = tasks_by_pursuit.get(pursuit.id, [])
        p_cal = cal_by_pursuit.get(pursuit.id, [])
        score = score_by_spark.get(spark.id)
        form_pkg = pkg_by_pursuit.get(pursuit.id)
        disqualified = bool(score and score.disqualified)
        blocked = [t for t in p_tasks if t.status == "blocked"]
        open_tasks = [t for t in p_tasks if t.status not in {"done", "cancelled"}]
        stages, current_id = build_pursuit_stages(
            has_profile=has_profile,
            has_req=int(req_count.get(spark.id, 0)) > 0,
            has_score=score is not None,
            disqualified=disqualified,
            has_pursuit=True,
            has_form=form_pkg is not None,
            blocked_tasks=bool(blocked),
        )
        nxt = _next_action(
            has_profile=has_profile,
            has_req=int(req_count.get(spark.id, 0)) > 0,
            has_score=score is not None,
            has_pursuit=True,
            has_form=form_pkg is not None,
            open_task=open_tasks[0] if open_tasks else None,
            blocked=blocked[0] if blocked else None,
        )
        last_activity = _aware(pursuit.updated_at)
        for task in p_tasks:
            last_activity = max(
                filter(None, [last_activity, _aware(task.updated_at)]),
                default=last_activity,
            )
        for row in ixn_by_spark.get(spark.id, []):
            occurred = datetime.fromisoformat(
                str(row["occurred_at"]).replace("Z", "+00:00")
            )
            last_activity = max(
                filter(None, [last_activity, _aware(occurred)]),
                default=last_activity,
            )

        stalled = False
        stalled_reason = None
        if (
            pursuit.status == "active"
            and open_tasks
            and last_activity
            and now - last_activity >= STALE_AFTER
        ):
            stalled = True
            stalled_reason = "No recorded activity in 14 days while work remains open"

        app_due = _aware(spark.application_deadline)
        days_to_deadline = _days(app_due, now=now)

        active_cards.append(
            {
                "pursuit_id": str(pursuit.id),
                "grant_spark_id": str(spark.id),
                "title": spark.opportunity_title,
                "funder": spark.agency,
                "status": pursuit.status,
                "deadline": _iso(spark.application_deadline),
                "current_stage_id": current_id,
                "stages": stages,
                "next_action": nxt,
                "open_count": len(open_tasks),
                "blocked_count": len(blocked),
                "overdue_count": sum(
                    1
                    for t in open_tasks
                    if _aware(t.due_at) is not None and _aware(t.due_at) < now
                ),
                "stalled": stalled,
                "stalled_reason": stalled_reason,
                "last_activity": _iso(last_activity),
                "view": "pursuits",
            }
        )

        for task in p_tasks:
            if task.status == "done":
                if (
                    _aware(task.completed_at)
                    and now - _aware(task.completed_at) <= STALE_AFTER
                ):
                    recently.append(
                        {
                            "id": str(task.id),
                            "title": task.title,
                            "completed_at": _iso(task.completed_at),
                            "grant_spark_id": str(spark.id),
                            "opportunity_title": spark.opportunity_title,
                        }
                    )
                continue
            if task.status == "cancelled":
                continue
            due = _aware(task.due_at)
            days = _days(due, now=now)
            attention = "in_progress"
            explanation = "Open task on this pursuit"
            rank = 9
            if task.status == "blocked":
                attention = "blocked"
                explanation = (
                    f"Blocked — application due in {days_to_deadline} days"
                    if days_to_deadline is not None and days_to_deadline <= 7
                    else "A task is blocked"
                )
                rank = (
                    1 if days_to_deadline is not None and days_to_deadline <= 7 else 3
                )
            elif due is not None and due < now:
                attention = "overdue"
                explanation = "Overdue work"
                rank = 2
            elif due is not None and due - now <= DUE_SOON:
                attention = "due_soon"
                explanation = "Due within 7 days"
                rank = 7
            elif task.status == "pending":
                attention = "ready"
                explanation = "Ready to begin"
                rank = 9
            work.append(
                _item(
                    kind="task",
                    attention=attention,
                    title=task.title,
                    detail=task.description or "Pursuit task",
                    explanation=explanation,
                    rank=rank,
                    spark=spark,
                    pursuit=pursuit,
                    stage_id=current_id,
                    status=task.status,
                    due_at=due,
                    days=days,
                    owner_membership_id=getattr(task, "owner_membership_id", None),
                    source_id=str(task.id),
                    view="pursuits",
                    now=now,
                )
            )

        if form_pkg is not None:
            artifact = art_by_id.get(form_pkg.review_artifact_id)
            if artifact and artifact.review_status in {
                "draft",
                "pending_review",
            }:
                work.append(
                    _item(
                        kind="review",
                        attention="needs_review",
                        title="Package awaiting review",
                        detail=f"Review status: {artifact.review_status}",
                        explanation=(
                            "Review required near submission"
                            if days_to_deadline is not None and days_to_deadline <= 14
                            else "Application package is waiting on review"
                        ),
                        rank=4
                        if days_to_deadline is not None and days_to_deadline <= 14
                        else 8,
                        spark=spark,
                        pursuit=pursuit,
                        stage_id="trust",
                        status=artifact.review_status,
                        due_at=app_due,
                        days=days_to_deadline,
                        owner_membership_id=None,
                        source_id=str(artifact.id),
                        view="trust",
                        now=now,
                    )
                )

        for brief in briefs:
            if brief.pursuit_id != pursuit.id:
                continue
            if brief.status != "pending_review":
                continue
            work.append(
                _item(
                    kind="review",
                    attention="needs_review",
                    title="Pursuit brief awaiting review",
                    detail=brief.status,
                    explanation="Brief pending review",
                    rank=8,
                    spark=spark,
                    pursuit=pursuit,
                    stage_id="trust",
                    status=brief.status,
                    due_at=None,
                    days=None,
                    owner_membership_id=None,
                    source_id=str(brief.id),
                    view="pursuits",
                    now=now,
                )
            )

        for row in ixn_by_spark.get(spark.id, []):
            follow = row.get("follow_up_at")
            follow_dt = (
                datetime.fromisoformat(str(follow).replace("Z", "+00:00"))
                if follow
                else None
            )
            waiting = row.get("status") == "awaiting_reply" or (
                follow_dt is not None and _aware(follow_dt) is not None
            )
            if not waiting:
                continue
            follow_aware = _aware(follow_dt)
            past = follow_aware is not None and follow_aware <= now
            work.append(
                _item(
                    kind="follow_up",
                    attention="waiting" if not past else "overdue",
                    title=row.get("subject") or "Funder follow-up",
                    detail=row.get("notes") or row.get("interaction_type"),
                    explanation=(
                        "Follow-up due — awaiting agency response"
                        if past or row.get("status") == "awaiting_reply"
                        else "Waiting on the funder"
                    ),
                    rank=5 if past else 8,
                    spark=spark,
                    pursuit=pursuit,
                    stage_id=current_id,
                    status=row.get("status"),
                    due_at=follow_aware,
                    days=_days(follow_aware, now=now),
                    owner_membership_id=None,
                    owner_label=row.get("owner_label"),
                    source_id=str(row["id"]),
                    view="pursuits",
                    now=now,
                )
            )

        facts = extract_engagement_facts(spark.raw_nofo_text or "")
        for fact in facts:
            if fact["kind"] != "questions_due":
                continue
            work.append(
                _item(
                    kind="deadline",
                    attention="due_soon",
                    title="Questions due",
                    detail=str(fact["value"]),
                    explanation="Approaching question deadline (from notice text)",
                    rank=6,
                    spark=spark,
                    pursuit=pursuit,
                    stage_id=current_id,
                    status="open",
                    due_at=None,
                    days=None,
                    owner_membership_id=None,
                    source_id=f"questions-{spark.id}",
                    view="documents",
                    now=now,
                )
            )

        for event in p_cal:
            deadline_items.append(
                {
                    "kind": event.kind,
                    "label": event.title,
                    "occurs_at": _iso(event.occurs_at),
                    "bucket": _bucket(event.occurs_at, now=now),
                    "grant_spark_id": str(spark.id),
                    "opportunity_title": spark.opportunity_title,
                    "source": "pursuit calendar",
                }
            )
        if spark.application_deadline:
            deadline_items.append(
                {
                    "kind": "application_deadline",
                    "label": "Application deadline",
                    "occurs_at": _iso(spark.application_deadline),
                    "bucket": _bucket(spark.application_deadline, now=now),
                    "grant_spark_id": str(spark.id),
                    "opportunity_title": spark.opportunity_title,
                    "source": "opportunity record",
                }
            )
        if spark.loi_deadline:
            deadline_items.append(
                {
                    "kind": "loi_deadline",
                    "label": "Letter of interest",
                    "occurs_at": _iso(spark.loi_deadline),
                    "bucket": _bucket(spark.loi_deadline, now=now),
                    "grant_spark_id": str(spark.id),
                    "opportunity_title": spark.opportunity_title,
                    "source": "opportunity record",
                }
            )

        # Trust is never marked complete on the visual stage strip. Review
        # items already carry real pending_review evidence. Do not mint a
        # second work row for the unfinished graphic.
        if nxt["action_id"] not in {"task", "pursuit", "trust"} and not open_tasks:
            if nxt["action_id"] in {"nofo_extract", "score", "sf424", "profile"}:
                work.append(
                    _item(
                        kind="workflow",
                        attention="ready",
                        title=nxt["headline"],
                        detail=nxt["detail"],
                        explanation="Next canonical step on this pursuit",
                        rank=9,
                        spark=spark,
                        pursuit=pursuit,
                        stage_id=current_id,
                        status="ready",
                        due_at=app_due,
                        days=days_to_deadline,
                        owner_membership_id=None,
                        source_id=f"workflow-{pursuit.id}-{nxt['action_id']}",
                        view=nxt.get("view") or "pursuits",
                        now=now,
                    )
                )

        if stalled:
            work.append(
                _item(
                    kind="stalled",
                    attention="due_soon"
                    if days_to_deadline is not None
                    else "in_progress",
                    title=f"Stalled: {spark.opportunity_title}",
                    detail=stalled_reason,
                    explanation=stalled_reason or "Stalled pursuit",
                    rank=8,
                    spark=spark,
                    pursuit=pursuit,
                    stage_id=current_id,
                    status="stalled",
                    due_at=app_due,
                    days=days_to_deadline,
                    owner_membership_id=None,
                    source_id=f"stalled-{pursuit.id}",
                    view="pursuits",
                    now=now,
                )
            )

    work.sort(
        key=lambda item: (item["rank"], item.get("days") is None, item.get("days") or 0)
    )

    blocked = [w for w in work if w["attention"] == "blocked"]
    overdue = [w for w in work if w["attention"] == "overdue"]
    waiting = [w for w in work if w["kind"] == "follow_up"]
    review = [w for w in work if w["kind"] == "review"]
    due_week = [
        w for w in work if w.get("days") is not None and 0 <= int(w["days"]) <= 7
    ]

    next_item = work[0] if work else None
    empty = not pursuits
    caught_up = bool(pursuits) and not work

    next_deadline = None
    dated = [d for d in deadline_items if d.get("occurs_at")]
    dated.sort(key=lambda d: d["occurs_at"] or "")
    if dated:
        next_deadline = dated[0]

    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": now.isoformat(),
        "viewer_membership_id": str(viewer_membership_id)
        if viewer_membership_id
        else None,
        "metrics": {
            "active_pursuits": len(
                [p for p in pursuits if p.status in {"active", "paused"}]
            ),
            "open_work": len(work),
            "blocked": len(blocked),
            "overdue": len(overdue),
            "due_this_week": len(due_week),
            "awaiting_response": len(waiting),
            "needs_review": len(review),
        },
        "next": next_item,
        "open_work": work,
        "active_pursuits": active_cards,
        "blockers": blocked,
        "waiting": waiting,
        "reviews": review,
        "deadlines": dated,
        "recently_completed": sorted(
            recently, key=lambda r: r.get("completed_at") or "", reverse=True
        )[:12],
        "empty": empty,
        "caught_up": caught_up,
        "next_deadline": next_deadline,
        "queries": {
            "sparks": 1,
            "pursuits": 1,
            "tasks": 1,
            "calendar": 1,
            "scores": 1,
            "packages": 1,
            "artifacts": 1,
            "briefs": 1,
            "requirements": 1,
            "interactions": 1,
        },
    }


def _item(
    *,
    kind: str,
    attention: str,
    title: str,
    detail: str | None,
    explanation: str,
    rank: int,
    spark: NfGrantSpark,
    pursuit: NfGrantPursuit,
    stage_id: str | None,
    status: str | None,
    due_at: datetime | None,
    days: int | None,
    owner_membership_id: uuid.UUID | None,
    source_id: str,
    view: str,
    now: datetime,
    owner_label: str | None = None,
) -> dict[str, Any]:
    return {
        "id": source_id,
        "kind": kind,
        "attention": attention,
        "title": title,
        "detail": detail,
        "explanation": explanation,
        "rank": rank,
        "pursuit_id": str(pursuit.id),
        "grant_spark_id": str(spark.id),
        "opportunity_title": spark.opportunity_title,
        "funder": spark.agency,
        "stage_id": stage_id,
        "status": status,
        "due_at": _iso(due_at),
        "days": days,
        "bucket": _bucket(due_at, now=now),
        "owner_membership_id": str(owner_membership_id)
        if owner_membership_id
        else None,
        "owner_label": owner_label,
        "view": view,
    }
