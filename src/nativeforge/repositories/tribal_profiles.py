"""NF tribal profile persistence."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import delete
from sqlalchemy.orm import Session

from nativeforge.db.models import NfAuditEvent, NfTribalProfile
from nativeforge.domain.enums import AuditAction
from nativeforge.lib.demo_isolation import OrgType
from nativeforge.repositories.scoping import select_tribal_profile_for_org


def get_tribal_profile_for_org(
    *,
    session: Session,
    org_id: uuid.UUID,
    org_type: OrgType,
) -> NfTribalProfile | None:
    stmt = select_tribal_profile_for_org(org_id=org_id, org_type=org_type)
    return session.execute(stmt).scalar_one_or_none()


def append_profile_audit(
    *,
    session: Session,
    profile: NfTribalProfile,
    action: AuditAction,
    actor_id: uuid.UUID | None,
    payload: dict[str, Any] | None = None,
) -> NfAuditEvent:
    """Append an audit row tied to this tribal profile."""
    ev = NfAuditEvent(
        id=uuid.uuid4(),
        organization_id=profile.organization_id,
        is_demo=profile.is_demo,
        review_artifact_id=None,
        tribal_profile_id=profile.id,
        action=action.value,
        payload=payload or {},
        actor_id=actor_id,
    )
    session.add(ev)
    session.flush()
    return ev


def delete_tribal_profiles_for_org_ids(
    session: Session,
    org_ids: list[uuid.UUID],
) -> None:
    """Remove tribal profiles for org IDs (tests / teardown)."""
    if not org_ids:
        return
    session.execute(
        delete(NfTribalProfile).where(NfTribalProfile.organization_id.in_(org_ids))
    )
