"""NOFO extraction runs and checklist requirement rows."""

from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from nativeforge.db.models import NfNofoExtractionRun, NfSparkRequirement
from nativeforge.lib.demo_isolation import OrgType
from nativeforge.repositories.scoping import (
    select_latest_nofo_run_for_spark,
    select_requirements_for_extraction_run,
)


def get_latest_extraction_run(
    *,
    session: Session,
    spark_id: uuid.UUID,
    org_id: uuid.UUID,
    org_type: OrgType,
) -> NfNofoExtractionRun | None:
    stmt = select_latest_nofo_run_for_spark(
        spark_id=spark_id,
        org_id=org_id,
        org_type=org_type,
    )
    return session.scalar(stmt)


def list_requirements_for_run(
    *,
    session: Session,
    extraction_run_id: uuid.UUID,
    org_id: uuid.UUID,
    org_type: OrgType,
) -> list[NfSparkRequirement]:
    q = select_requirements_for_extraction_run(
        extraction_run_id=extraction_run_id,
        org_id=org_id,
        org_type=org_type,
    )
    return list(session.scalars(q))
