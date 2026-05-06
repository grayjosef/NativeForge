"""nf_form_packages — org-scoped."""

from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from nativeforge.db.models import NfFormPackage
from nativeforge.lib.demo_isolation import OrgType
from nativeforge.repositories.scoping import (
    select_form_package_for_pursuit,
    select_form_packages_for_org,
)


def list_form_packages_for_org(
    *,
    session: Session,
    org_id: uuid.UUID,
    org_type: OrgType,
) -> list[NfFormPackage]:
    q = select_form_packages_for_org(org_id=org_id, org_type=org_type)
    return list(session.scalars(q))


def get_form_package_for_pursuit(
    *,
    session: Session,
    pursuit_id: uuid.UUID,
    org_id: uuid.UUID,
    org_type: OrgType,
) -> NfFormPackage | None:
    stmt = select_form_package_for_pursuit(
        pursuit_id=pursuit_id,
        org_id=org_id,
        org_type=org_type,
    )
    return session.scalar(stmt)
