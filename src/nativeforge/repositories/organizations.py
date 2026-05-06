"""Organization lookups."""

from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from nativeforge.db.models import Organization


def get_organization(session: Session, org_id: uuid.UUID) -> Organization | None:
    return session.get(Organization, org_id)
