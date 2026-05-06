"""nf_pursuit_briefs — org-scoped persistence."""

from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from nativeforge.db.models import NfPursuitBrief
from nativeforge.lib.demo_isolation import OrgType
from nativeforge.repositories.scoping import (
    select_latest_pursuit_brief_for_pursuit,
    select_latest_pursuit_brief_for_spark,
)


def get_latest_for_spark(
    *,
    session: Session,
    spark_id: uuid.UUID,
    org_id: uuid.UUID,
    org_type: OrgType,
) -> NfPursuitBrief | None:
    stmt = select_latest_pursuit_brief_for_spark(
        spark_id=spark_id,
        org_id=org_id,
        org_type=org_type,
    )
    return session.scalar(stmt)


def get_latest_for_pursuit(
    *,
    session: Session,
    pursuit_id: uuid.UUID,
    org_id: uuid.UUID,
    org_type: OrgType,
) -> NfPursuitBrief | None:
    stmt = select_latest_pursuit_brief_for_pursuit(
        pursuit_id=pursuit_id,
        org_id=org_id,
        org_type=org_type,
    )
    return session.scalar(stmt)
