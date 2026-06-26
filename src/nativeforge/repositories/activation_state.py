"""M8: activation state repository (per-workspace durable row)."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from nativeforge.db.models import (
    NfActivationState,
    NfAuditEvent,
    NfAutoPublishConfig,
    is_demo_for_org_type,
)


def get_activation_state(
    session: Session,
    *,
    organization_id: uuid.UUID,
    is_demo: bool,
) -> NfActivationState | None:
    return session.scalar(
        select(NfActivationState).where(
            NfActivationState.organization_id == organization_id,
            NfActivationState.is_demo.is_(is_demo),
        )
    )


def get_or_create_activation_state(
    session: Session,
    *,
    organization_id: uuid.UUID,
    is_demo: bool,
) -> NfActivationState:
    row = get_activation_state(
        session, organization_id=organization_id, is_demo=is_demo
    )
    if row is not None:
        return row
    row = NfActivationState(
        organization_id=organization_id,
        is_demo=is_demo,
        live_publish_enabled=False,
        live_attribution_enabled=False,
        auto_publish_enabled=False,
        kill_switch_engaged=False,
        state_version=1,
    )
    session.add(row)
    session.flush()
    return row


def list_auto_publish_configs(
    session: Session,
    *,
    organization_id: uuid.UUID,
    is_demo: bool,
    limit: int = 20,
) -> list[NfAutoPublishConfig]:
    stmt = (
        select(NfAutoPublishConfig)
        .where(
            NfAutoPublishConfig.organization_id == organization_id,
            NfAutoPublishConfig.is_demo.is_(is_demo),
        )
        .order_by(NfAutoPublishConfig.version.desc())
        .limit(limit)
    )
    return list(session.scalars(stmt))


def get_latest_auto_publish_config(
    session: Session,
    *,
    organization_id: uuid.UUID,
    is_demo: bool,
) -> NfAutoPublishConfig | None:
    rows = list_auto_publish_configs(
        session, organization_id=organization_id, is_demo=is_demo, limit=1
    )
    return rows[0] if rows else None


def append_auto_publish_config(
    session: Session,
    *,
    organization_id: uuid.UUID,
    is_demo: bool,
    version: int,
    enabled: bool,
    reason: str,
    config_payload: dict[str, Any] | None,
    actor_id: uuid.UUID | None,
    actor_role: str,
) -> NfAutoPublishConfig:
    row = NfAutoPublishConfig(
        organization_id=organization_id,
        is_demo=is_demo,
        version=version,
        enabled=enabled,
        reason=reason,
        config_payload=config_payload,
        created_by_actor_id=actor_id,
        created_by_actor_role=actor_role,
    )
    session.add(row)
    session.flush()
    return row


def append_activation_audit(
    session: Session,
    *,
    organization_id: uuid.UUID,
    org_type: str,
    action: str,
    payload: dict[str, Any],
    actor_id: uuid.UUID | None,
) -> NfAuditEvent:
    ev = NfAuditEvent(
        organization_id=organization_id,
        is_demo=is_demo_for_org_type(org_type),
        action=action,
        payload=payload,
        actor_id=actor_id,
    )
    session.add(ev)
    session.flush()
    return ev


def list_activation_audit_events(
    session: Session,
    *,
    organization_id: uuid.UUID,
    is_demo: bool,
    limit: int = 25,
) -> list[NfAuditEvent]:
    prefix = "activation_"
    stmt = (
        select(NfAuditEvent)
        .where(
            NfAuditEvent.organization_id == organization_id,
            NfAuditEvent.is_demo.is_(is_demo),
            NfAuditEvent.action.like(f"{prefix}%"),
        )
        .order_by(NfAuditEvent.created_at.desc())
        .limit(limit)
    )
    return list(session.scalars(stmt))
