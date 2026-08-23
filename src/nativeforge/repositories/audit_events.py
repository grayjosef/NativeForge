"""nf_audit_events — org-scoped reads + append."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.orm import Session

from nativeforge.db.models import NfAuditEvent
from nativeforge.domain.enums import UNPERSISTABLE_AUDIT_ACTIONS, AuditAction
from nativeforge.lib.demo_isolation import OrgType
from nativeforge.repositories.scoping import select_audit_events_for_org


def list_audit_events_for_org(
    *,
    session: Session,
    org_id: uuid.UUID,
    org_type: OrgType,
    limit: int,
) -> list[NfAuditEvent]:
    stmt = select_audit_events_for_org(org_id=org_id, org_type=org_type, limit=limit)
    return list(session.scalars(stmt))


def audit_event_to_dict(ev: NfAuditEvent) -> dict[str, Any]:
    def _dt(v: object | None) -> str | None:
        if v is None:
            return None
        if hasattr(v, "isoformat"):
            return v.isoformat()  # type: ignore[no-any-return]
        return str(v)

    return {
        "id": str(ev.id),
        "action": ev.action,
        "payload": ev.payload,
        "actor_id": str(ev.actor_id) if ev.actor_id else None,
        "review_artifact_id": str(ev.review_artifact_id)
        if ev.review_artifact_id
        else None,
        "tribal_profile_id": str(ev.tribal_profile_id)
        if ev.tribal_profile_id
        else None,
        "extraction_run_id": str(ev.extraction_run_id)
        if ev.extraction_run_id
        else None,
        "created_at": _dt(ev.created_at),
    }


def append_org_audit_event(
    session: Session,
    *,
    organization_id: uuid.UUID,
    is_demo: bool,
    action: AuditAction,
    payload: dict[str, Any] | None,
    actor_id: uuid.UUID | None,
) -> NfAuditEvent:
    # Some security verbs cannot be represented correctly by this table yet.
    # cross_org_access_attempt involves two organizations and this table has one
    # NOT NULL, RLS-scoped organization_id column: writing it would either hide
    # the event from the tenant that was attacked or attribute the attack to
    # them. Refusing is the honest option until migration 0028 lands.
    #
    # This raises rather than silently dropping. A security event that vanishes
    # is worse than a request that fails, because nobody finds out.
    if action in UNPERSISTABLE_AUDIT_ACTIONS:
        raise ValueError(
            f"audit action {action.value!r} cannot be persisted by the current "
            "nf_audit_events schema: it needs distinct actor/target organization "
            "columns. See docs/operations/"
            "401_GATE65_AUDIT_ACTION_VOCABULARY_AND_0028_PLAN.md"
        )
    ev = NfAuditEvent(
        id=uuid.uuid4(),
        organization_id=organization_id,
        is_demo=is_demo,
        review_artifact_id=None,
        tribal_profile_id=None,
        extraction_run_id=None,
        action=action.value,
        payload=payload or {},
        actor_id=actor_id,
    )
    session.add(ev)
    session.flush()
    return ev
