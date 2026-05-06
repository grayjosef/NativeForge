"""nf_source_check_runs — org-scoped source check records."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import Session

from nativeforge.db.models import NfSourceCheckRun
from nativeforge.lib.demo_isolation import OrgType
from nativeforge.repositories.scoping import (
    select_source_check_run_scoped,
    select_source_check_runs_for_org,
    select_source_check_runs_for_source,
)


def create_source_check_run(
    session: Session,
    *,
    organization_id: uuid.UUID,
    is_demo: bool,
    source_registry_id: uuid.UUID,
    check_mode: str,
    check_status: str,
    operator_notes: str | None = None,
    checked_for_period_start: datetime | None = None,
    checked_for_period_end: datetime | None = None,
    started_at: datetime | None = None,
) -> NfSourceCheckRun:
    row = NfSourceCheckRun(
        organization_id=organization_id,
        is_demo=is_demo,
        source_registry_id=source_registry_id,
        check_mode=check_mode,
        check_status=check_status,
        operator_notes=operator_notes,
        checked_for_period_start=checked_for_period_start,
        checked_for_period_end=checked_for_period_end,
        started_at=started_at or datetime.now(UTC),
    )
    session.add(row)
    session.flush()
    return row


def get_source_check_run_scoped(
    session: Session,
    *,
    check_run_id: uuid.UUID,
    org_id: uuid.UUID,
    org_type: OrgType,
) -> NfSourceCheckRun | None:
    stmt = select_source_check_run_scoped(
        org_id=org_id,
        org_type=org_type,
        check_run_id=check_run_id,
    )
    return session.scalar(stmt)


def list_source_check_runs_for_org(
    session: Session,
    *,
    org_id: uuid.UUID,
    org_type: OrgType,
    limit: int = 500,
) -> list[NfSourceCheckRun]:
    stmt = select_source_check_runs_for_org(org_id=org_id, org_type=org_type).limit(
        limit
    )
    return list(session.scalars(stmt))


def list_source_check_runs_for_source(
    session: Session,
    *,
    org_id: uuid.UUID,
    org_type: OrgType,
    source_registry_id: uuid.UUID,
    limit: int = 500,
) -> list[NfSourceCheckRun]:
    stmt = select_source_check_runs_for_source(
        org_id=org_id,
        org_type=org_type,
        source_registry_id=source_registry_id,
    ).limit(limit)
    return list(session.scalars(stmt))


def complete_source_check_run(
    session: Session,
    row: NfSourceCheckRun,
    **kwargs: Any,
) -> NfSourceCheckRun:
    for k, v in kwargs.items():
        if hasattr(row, k):
            setattr(row, k, v)
    session.flush()
    return row
