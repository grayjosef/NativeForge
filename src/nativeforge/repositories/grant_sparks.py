"""nf_grant_sparks persistence — org-scoped queries only."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from nativeforge.db.models import NfGrantSpark
from nativeforge.lib.demo_isolation import OrgType
from nativeforge.repositories.scoping import (
    nf_grant_spark_scope,
    select_grant_sparks_for_org,
)


def list_grant_sparks_for_org(
    *,
    session: Session,
    org_id: uuid.UUID,
    org_type: OrgType,
) -> list[NfGrantSpark]:
    q = select_grant_sparks_for_org(org_id=org_id, org_type=org_type)
    return list(session.scalars(q))


def get_grant_spark_scoped(
    *,
    session: Session,
    spark_id: uuid.UUID,
    org_id: uuid.UUID,
    org_type: OrgType,
) -> NfGrantSpark | None:
    scope = nf_grant_spark_scope(org_id=org_id, org_type=org_type)
    stmt = select(NfGrantSpark).where(NfGrantSpark.id == spark_id, *scope)
    return session.scalar(stmt)


def find_grant_spark_by_duplicate_key(
    *,
    session: Session,
    duplicate_key: str,
    org_id: uuid.UUID,
    org_type: OrgType,
) -> NfGrantSpark | None:
    scope = nf_grant_spark_scope(org_id=org_id, org_type=org_type)
    stmt = (
        select(NfGrantSpark)
        .where(NfGrantSpark.duplicate_key == duplicate_key, *scope)
        .limit(1)
    )
    return session.scalar(stmt)


def find_grant_spark_by_source_key(
    *,
    session: Session,
    org_id: uuid.UUID,
    org_type: OrgType,
    source: str,
    source_id: str,
) -> NfGrantSpark | None:
    scope = nf_grant_spark_scope(org_id=org_id, org_type=org_type)
    stmt = (
        select(NfGrantSpark)
        .where(
            NfGrantSpark.source == source,
            NfGrantSpark.source_id == source_id,
            *scope,
        )
        .limit(1)
    )
    return session.scalar(stmt)
