"""M7/M8: activation state read model + governed mutations."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.orm import Session

from nativeforge.db.models import NfActivationState
from nativeforge.repositories import activation_state as activation_repo
from nativeforge.repositories.audit_events import audit_event_to_dict
from nativeforge.services.activation_principal_service import ActivationPrincipal
from nativeforge.services.activation_publish_gate_service import evaluate_publish_gate

SCHEMA_VERSION = "nf_activation_state_v1"


def activation_state_to_dict(
    row: NfActivationState,
    *,
    publish_gate: dict[str, Any] | None = None,
    auto_publish_config_version: int | None = None,
    recent_audit: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    gate = publish_gate or {}
    return {
        "schema_version": SCHEMA_VERSION,
        "organization_id": str(row.organization_id),
        "is_demo": row.is_demo,
        "live_publish_enabled": row.live_publish_enabled,
        "live_attribution_enabled": row.live_attribution_enabled,
        "auto_publish_enabled": row.auto_publish_enabled,
        "kill_switch_engaged": row.kill_switch_engaged,
        "current_auto_publish_config_version": (
            auto_publish_config_version or row.current_auto_publish_config_version
        ),
        "state_version": row.state_version,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
        "updated_by_actor_id": (
            str(row.updated_by_actor_id) if row.updated_by_actor_id else None
        ),
        "updated_by_actor_role": row.updated_by_actor_role,
        "publish_gate": gate,
        "recent_audit": recent_audit or [],
        "defaults_off": not any(
            (
                row.live_publish_enabled,
                row.live_attribution_enabled,
                row.auto_publish_enabled,
                row.kill_switch_engaged,
            )
        ),
    }


def build_activation_state_view(
    session: Session,
    *,
    organization_id: uuid.UUID,
    is_demo: bool,
    org_type: str,
) -> dict[str, Any]:
    row = activation_repo.get_or_create_activation_state(
        session,
        organization_id=organization_id,
        is_demo=is_demo,
    )
    latest = activation_repo.get_latest_auto_publish_config(
        session,
        organization_id=organization_id,
        is_demo=is_demo,
    )
    audit_rows = activation_repo.list_activation_audit_events(
        session,
        organization_id=organization_id,
        is_demo=is_demo,
        limit=15,
    )
    gate = evaluate_publish_gate(row)
    return activation_state_to_dict(
        row,
        publish_gate={
            "publish_permitted": gate.publish_permitted,
            "auto_publish_queue_permitted": gate.auto_publish_queue_permitted,
            "live_attribution_permitted": gate.live_attribution_permitted,
            "kill_switch_engaged": gate.kill_switch_engaged,
            "halt_reason": gate.halt_reason,
        },
        auto_publish_config_version=(
            latest.version if latest is not None else row.current_auto_publish_config_version
        ),
        recent_audit=[audit_event_to_dict(ev) for ev in audit_rows],
    )


def _bump_state(
    row: NfActivationState,
    *,
    principal: ActivationPrincipal,
) -> None:
    row.state_version = int(row.state_version or 0) + 1
    row.updated_by_actor_id = principal.actor_id
    row.updated_by_actor_role = principal.actor_role.value


def _record_audit(
    session: Session,
    *,
    organization_id: uuid.UUID,
    org_type: str,
    action: str,
    payload: dict[str, Any],
    principal: ActivationPrincipal,
) -> None:
    activation_repo.append_activation_audit(
        session,
        organization_id=organization_id,
        org_type=org_type,
        action=action,
        payload=payload,
        actor_id=principal.actor_id,
    )


def apply_kill_switch(
    session: Session,
    *,
    organization_id: uuid.UUID,
    is_demo: bool,
    org_type: str,
    principal: ActivationPrincipal,
    engaged: bool,
) -> dict[str, Any]:
    row = activation_repo.get_or_create_activation_state(
        session,
        organization_id=organization_id,
        is_demo=is_demo,
    )
    row.kill_switch_engaged = engaged
    _bump_state(row, principal=principal)
    action = "activation_kill_switch_engaged" if engaged else "activation_kill_switch_released"
    _record_audit(
        session,
        organization_id=organization_id,
        org_type=org_type,
        action=action,
        payload={
            "kill_switch_engaged": engaged,
            "state_version": row.state_version,
        },
        principal=principal,
    )
    session.flush()
    return build_activation_state_view(
        session,
        organization_id=organization_id,
        is_demo=is_demo,
        org_type=org_type,
    )


def apply_flag_toggle(
    session: Session,
    *,
    organization_id: uuid.UUID,
    is_demo: bool,
    org_type: str,
    principal: ActivationPrincipal,
    flag: str,
    enabled: bool,
    reason: str | None = None,
) -> dict[str, Any]:
    row = activation_repo.get_or_create_activation_state(
        session,
        organization_id=organization_id,
        is_demo=is_demo,
    )
    if flag == "live_publish":
        row.live_publish_enabled = enabled
    elif flag == "live_attribution":
        row.live_attribution_enabled = enabled
    elif flag == "auto_publish":
        row.auto_publish_enabled = enabled
        if not enabled:
            row.current_auto_publish_config_version = None
    else:
        raise ValueError(f"unknown activation flag: {flag!r}")

    _bump_state(row, principal=principal)
    _record_audit(
        session,
        organization_id=organization_id,
        org_type=org_type,
        action=f"activation_flag_{flag}_{'enabled' if enabled else 'disabled'}",
        payload={
            "flag": flag,
            "enabled": enabled,
            "reason": reason,
            "state_version": row.state_version,
        },
        principal=principal,
    )
    session.flush()
    return build_activation_state_view(
        session,
        organization_id=organization_id,
        is_demo=is_demo,
        org_type=org_type,
    )


def apply_auto_publish_policy_enable(
    session: Session,
    *,
    organization_id: uuid.UUID,
    is_demo: bool,
    org_type: str,
    principal: ActivationPrincipal,
    reason: str,
    config_payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    row = activation_repo.get_or_create_activation_state(
        session,
        organization_id=organization_id,
        is_demo=is_demo,
    )
    latest = activation_repo.get_latest_auto_publish_config(
        session,
        organization_id=organization_id,
        is_demo=is_demo,
    )
    next_version = (latest.version + 1) if latest is not None else 1
    config_row = activation_repo.append_auto_publish_config(
        session,
        organization_id=organization_id,
        is_demo=is_demo,
        version=next_version,
        enabled=True,
        reason=reason,
        config_payload=config_payload,
        actor_id=principal.actor_id,
        actor_role=principal.actor_role.value,
    )
    row.auto_publish_enabled = True
    row.current_auto_publish_config_version = config_row.version
    _bump_state(row, principal=principal)
    _record_audit(
        session,
        organization_id=organization_id,
        org_type=org_type,
        action="activation_policy_auto_publish_enabled",
        payload={
            "auto_publish_config_version": config_row.version,
            "reason": reason,
            "state_version": row.state_version,
        },
        principal=principal,
    )
    session.flush()
    return build_activation_state_view(
        session,
        organization_id=organization_id,
        is_demo=is_demo,
        org_type=org_type,
    )
