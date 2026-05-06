"""nf_operator_actions — org-scoped CRUD and ledger queries."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session

from nativeforge.db.models import NfOperatorAction
from nativeforge.domain.enums import OperatorActionStatus
from nativeforge.lib.demo_isolation import OrgType
from nativeforge.repositories.scoping import (
    nf_operator_action_scope,
    select_operator_action_scoped,
    select_operator_actions_for_org,
)

_ACTIVE_DECISION_STATUSES = frozenset(
    {
        OperatorActionStatus.open.value,
        OperatorActionStatus.in_progress.value,
        OperatorActionStatus.deferred.value,
        OperatorActionStatus.reopened.value,
    }
)


def create_operator_action(
    session: Session,
    row: NfOperatorAction,
) -> NfOperatorAction:
    session.add(row)
    session.flush()
    return row


def get_operator_action_scoped(
    session: Session,
    *,
    action_id: uuid.UUID,
    org_id: uuid.UUID,
    org_type: OrgType,
) -> NfOperatorAction | None:
    stmt = select_operator_action_scoped(
        org_id=org_id,
        org_type=org_type,
        operator_action_id=action_id,
    )
    return session.scalar(stmt)


def list_operator_actions_for_org(
    session: Session,
    *,
    org_id: uuid.UUID,
    org_type: OrgType,
    status: str | None = None,
    severity: str | None = None,
    item_type: str | None = None,
    action: str | None = None,
    assigned_to: str | None = None,
    source_registry_id: uuid.UUID | None = None,
    review_item_id: uuid.UUID | None = None,
    intake_run_id: uuid.UUID | None = None,
    decision_id: str | None = None,
    open_only: bool = False,
    limit: int = 50,
) -> list[NfOperatorAction]:
    stmt = select_operator_actions_for_org(org_id=org_id, org_type=org_type)
    filters: list[Any] = []
    if status is not None:
        filters.append(NfOperatorAction.status == status)
    if severity is not None:
        filters.append(NfOperatorAction.severity == severity)
    if item_type is not None:
        filters.append(NfOperatorAction.item_type == item_type)
    if action is not None:
        filters.append(NfOperatorAction.action == action)
    if assigned_to is not None:
        filters.append(NfOperatorAction.assigned_to == assigned_to)
    if source_registry_id is not None:
        filters.append(NfOperatorAction.source_registry_id == source_registry_id)
    if review_item_id is not None:
        filters.append(NfOperatorAction.review_item_id == review_item_id)
    if intake_run_id is not None:
        filters.append(NfOperatorAction.intake_run_id == intake_run_id)
    if decision_id is not None:
        filters.append(NfOperatorAction.decision_id == decision_id)
    if open_only:
        filters.append(NfOperatorAction.status.in_(_ACTIVE_DECISION_STATUSES))
    q = stmt
    if filters:
        q = q.where(and_(*filters))
    q = q.limit(limit)
    return list(session.scalars(q))


def list_active_operator_actions_for_decision(
    session: Session,
    *,
    org_id: uuid.UUID,
    org_type: OrgType,
    decision_id: str,
) -> list[NfOperatorAction]:
    scope = nf_operator_action_scope(org_id=org_id, org_type=org_type)
    stmt = (
        select(NfOperatorAction)
        .where(
            *scope,
            NfOperatorAction.decision_id == decision_id,
            NfOperatorAction.status.in_(_ACTIVE_DECISION_STATUSES),
        )
        .order_by(NfOperatorAction.updated_at.desc())
    )
    return list(session.scalars(stmt))


def find_active_operator_action_by_decision_id(
    session: Session,
    *,
    org_id: uuid.UUID,
    org_type: OrgType,
    decision_id: str,
) -> NfOperatorAction | None:
    rows = list_active_operator_actions_for_decision(
        session,
        org_id=org_id,
        org_type=org_type,
        decision_id=decision_id,
    )
    return rows[0] if rows else None


def update_operator_action(
    session: Session,
    row: NfOperatorAction,
) -> NfOperatorAction:
    session.add(row)
    session.flush()
    return row


def count_operator_actions_by_status(
    session: Session,
    *,
    org_id: uuid.UUID,
    org_type: OrgType,
) -> dict[str, int]:
    scope = nf_operator_action_scope(org_id=org_id, org_type=org_type)
    stmt = (
        select(NfOperatorAction.status, func.count())
        .where(*scope)
        .group_by(NfOperatorAction.status)
    )
    out: dict[str, int] = {}
    for st, cnt in session.execute(stmt).all():
        out[str(st)] = int(cnt)
    return out


def list_operator_actions_for_decision_ids(
    session: Session,
    *,
    org_id: uuid.UUID,
    org_type: OrgType,
    decision_ids: list[str],
    active_only: bool = True,
) -> list[NfOperatorAction]:
    if not decision_ids:
        return []
    scope = nf_operator_action_scope(org_id=org_id, org_type=org_type)
    stmt = select(NfOperatorAction).where(
        *scope,
        NfOperatorAction.decision_id.in_(decision_ids),
    )
    if active_only:
        stmt = stmt.where(NfOperatorAction.status.in_(_ACTIVE_DECISION_STATUSES))
    return list(session.scalars(stmt))


def count_resolved_since(
    session: Session,
    *,
    org_id: uuid.UUID,
    org_type: OrgType,
    since: datetime,
) -> int:
    scope = nf_operator_action_scope(org_id=org_id, org_type=org_type)
    stmt = (
        select(func.count())
        .select_from(NfOperatorAction)
        .where(
            *scope,
            NfOperatorAction.status == OperatorActionStatus.resolved.value,
            NfOperatorAction.resolved_at.is_not(None),
            NfOperatorAction.resolved_at >= since,
        )
    )
    return int(session.scalar(stmt) or 0)
