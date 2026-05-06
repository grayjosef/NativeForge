"""nf_grant_pursuits, tasks, calendar — org-scoped queries only."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from nativeforge.db.models import (
    NfAuditEvent,
    NfGrantPursuit,
    NfPursuitCalendarEvent,
    NfPursuitTask,
)
from nativeforge.domain.enums import AuditAction
from nativeforge.lib.demo_isolation import OrgType
from nativeforge.repositories.scoping import (
    nf_grant_pursuit_scope,
    nf_pursuit_calendar_scope,
    nf_pursuit_task_scope,
    select_calendar_events_for_org_between,
    select_grant_pursuits_for_org,
)


def append_pursuit_audit(
    session: Session,
    *,
    organization_id: uuid.UUID,
    is_demo: bool,
    action: AuditAction,
    payload: dict[str, Any] | None,
    actor_id: uuid.UUID | None,
) -> NfAuditEvent:
    ev = NfAuditEvent(
        id=uuid.uuid4(),
        organization_id=organization_id,
        is_demo=is_demo,
        review_artifact_id=None,
        tribal_profile_id=None,
        extraction_run_id=None,
        action=action.value,
        payload=payload or {},
        actor_id=actor_id,
    )
    session.add(ev)
    session.flush()
    return ev


def list_grant_pursuits(
    *,
    session: Session,
    org_id: uuid.UUID,
    org_type: OrgType,
) -> list[NfGrantPursuit]:
    q = select_grant_pursuits_for_org(org_id=org_id, org_type=org_type)
    return list(session.scalars(q))


def get_grant_pursuit_scoped(
    *,
    session: Session,
    pursuit_id: uuid.UUID,
    org_id: uuid.UUID,
    org_type: OrgType,
) -> NfGrantPursuit | None:
    scope = nf_grant_pursuit_scope(org_id=org_id, org_type=org_type)
    stmt = select(NfGrantPursuit).where(NfGrantPursuit.id == pursuit_id, *scope)
    return session.scalar(stmt)


def get_grant_pursuit_by_spark(
    *,
    session: Session,
    spark_id: uuid.UUID,
    org_id: uuid.UUID,
    org_type: OrgType,
) -> NfGrantPursuit | None:
    scope = nf_grant_pursuit_scope(org_id=org_id, org_type=org_type)
    stmt = select(NfGrantPursuit).where(
        NfGrantPursuit.grant_spark_id == spark_id,
        *scope,
    )
    return session.scalar(stmt)


def list_tasks_for_pursuit(
    *,
    session: Session,
    pursuit_id: uuid.UUID,
    org_id: uuid.UUID,
    org_type: OrgType,
) -> list[NfPursuitTask]:
    scope = nf_pursuit_task_scope(org_id=org_id, org_type=org_type)
    stmt = (
        select(NfPursuitTask)
        .where(NfPursuitTask.grant_pursuit_id == pursuit_id)
        .where(*scope)
        .order_by(NfPursuitTask.sort_order.asc(), NfPursuitTask.created_at.asc())
    )
    return list(session.scalars(stmt))


def get_task_scoped(
    *,
    session: Session,
    pursuit_id: uuid.UUID,
    task_id: uuid.UUID,
    org_id: uuid.UUID,
    org_type: OrgType,
) -> NfPursuitTask | None:
    scope = nf_pursuit_task_scope(org_id=org_id, org_type=org_type)
    stmt = select(NfPursuitTask).where(
        NfPursuitTask.id == task_id,
        NfPursuitTask.grant_pursuit_id == pursuit_id,
        *scope,
    )
    return session.scalar(stmt)


def list_calendar_for_pursuit(
    *,
    session: Session,
    pursuit_id: uuid.UUID,
    org_id: uuid.UUID,
    org_type: OrgType,
) -> list[NfPursuitCalendarEvent]:
    scope = nf_pursuit_calendar_scope(org_id=org_id, org_type=org_type)
    stmt = (
        select(NfPursuitCalendarEvent)
        .where(NfPursuitCalendarEvent.grant_pursuit_id == pursuit_id)
        .where(*scope)
        .order_by(NfPursuitCalendarEvent.occurs_at.asc())
    )
    return list(session.scalars(stmt))


def list_calendar_for_org_window(
    *,
    session: Session,
    org_id: uuid.UUID,
    org_type: OrgType,
    start_at: datetime,
    end_at: datetime,
) -> list[NfPursuitCalendarEvent]:
    q = select_calendar_events_for_org_between(
        org_id=org_id,
        org_type=org_type,
        start_at=start_at,
        end_at=end_at,
    )
    return list(session.scalars(q))
