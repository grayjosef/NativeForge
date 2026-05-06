"""nf_spark_scores persistence — org-scoped only."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from nativeforge.db.models import NfAuditEvent, NfSparkScore
from nativeforge.domain.enums import AuditAction
from nativeforge.lib.demo_isolation import OrgType
from nativeforge.repositories.scoping import (
    nf_spark_score_scope,
    select_latest_spark_score_for_spark,
)


def get_latest_spark_score(
    *,
    session: Session,
    spark_id: uuid.UUID,
    org_id: uuid.UUID,
    org_type: OrgType,
) -> NfSparkScore | None:
    stmt = select_latest_spark_score_for_spark(
        spark_id=spark_id,
        org_id=org_id,
        org_type=org_type,
    )
    return session.scalar(stmt)


def get_spark_score_for_spark(
    *,
    session: Session,
    score_id: uuid.UUID,
    spark_id: uuid.UUID,
    org_id: uuid.UUID,
    org_type: OrgType,
) -> NfSparkScore | None:
    scope = nf_spark_score_scope(org_id=org_id, org_type=org_type)
    stmt = select(NfSparkScore).where(
        NfSparkScore.id == score_id,
        NfSparkScore.grant_spark_id == spark_id,
        *scope,
    )
    return session.scalar(stmt)


def append_spark_score_audit(
    session: Session,
    *,
    organization_id: uuid.UUID,
    is_demo: bool,
    tribal_profile_id: uuid.UUID | None,
    extraction_run_id: uuid.UUID | None,
    action: AuditAction,
    payload: dict[str, Any] | None,
    actor_id: uuid.UUID | None,
) -> NfAuditEvent:
    ev = NfAuditEvent(
        id=uuid.uuid4(),
        organization_id=organization_id,
        is_demo=is_demo,
        review_artifact_id=None,
        tribal_profile_id=tribal_profile_id,
        extraction_run_id=extraction_run_id,
        action=action.value,
        payload=payload or {},
        actor_id=actor_id,
    )
    session.add(ev)
    session.flush()
    return ev


def apply_override_to_score(
    session: Session,
    *,
    row: NfSparkScore,
    reason: str,
    actor_id: uuid.UUID | None,
) -> NfSparkScore:
    row.override_reason = reason
    row.override_actor_id = actor_id
    row.overridden_at = datetime.now(UTC)
    session.flush()
    return row
