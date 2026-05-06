"""nf_opportunity_sources — org-scoped source registry queries."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from nativeforge.db.models import NfOpportunitySource
from nativeforge.lib.demo_isolation import OrgType
from nativeforge.repositories.scoping import (
    nf_opportunity_source_scope,
    select_opportunity_sources_for_org,
)


def list_opportunity_sources_for_org(
    *,
    session: Session,
    org_id: uuid.UUID,
    org_type: OrgType,
) -> list[NfOpportunitySource]:
    q = select_opportunity_sources_for_org(org_id=org_id, org_type=org_type)
    return list(session.scalars(q))


def get_opportunity_source_scoped(
    *,
    session: Session,
    source_id: uuid.UUID,
    org_id: uuid.UUID,
    org_type: OrgType,
) -> NfOpportunitySource | None:
    scope = nf_opportunity_source_scope(org_id=org_id, org_type=org_type)
    stmt = select(NfOpportunitySource).where(
        NfOpportunitySource.id == source_id,
        *scope,
    )
    return session.scalar(stmt)
