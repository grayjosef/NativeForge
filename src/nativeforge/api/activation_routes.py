"""M8: operator activation console API routes."""

from __future__ import annotations

import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from nativeforge.api.deps_db import (
    get_db_session,
    require_demo_org_db,
    require_real_org_db,
)
from nativeforge.api.org_context import OrgContext
from nativeforge.domain.enums import (
    ActivationToggleKey,
    GovernedActionKind,
    WorkspaceActorRole,
)
from nativeforge.repositories import activation_state as activation_repo
from nativeforge.services.activation_principal_service import (
    resolve_activation_principal_for_governed_action,
)
from nativeforge.services.activation_publish_gate_service import (
    ActivationPublishHaltedError,
    assert_auto_publish_queue_permitted,
    assert_live_publish_permitted,
)
from nativeforge.services.activation_state_service import build_activation_state_view
from nativeforge.services.governed_activation_dispatcher_service import (
    GovernedActivationValidationError,
    dispatch_governed_activation_action,
)

demo_activation_router = APIRouter(
    prefix="/v1/nf/demo/orgs",
    tags=["operator-activation-demo"],
)
real_activation_router = APIRouter(
    prefix="/v1/nf/real/orgs",
    tags=["operator-activation-real"],
)


def _same_org(path_org: uuid.UUID, ctx: OrgContext) -> None:
    if path_org != ctx.org_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="path org_id does not match authenticated org",
        )


class GovernedActivationBody(BaseModel):
    governed_action: GovernedActionKind
    toggle: ActivationToggleKey
    value: bool
    reason: str | None = Field(default=None, max_length=4096)
    config_payload: dict[str, Any] | None = None


def _parse_actor_role_header(
    x_nf_actor_role: str | None = Header(default=None, alias="X-NF-Actor-Role"),
) -> WorkspaceActorRole | None:
    if not x_nf_actor_role:
        return None
    raw = x_nf_actor_role.strip().lower()
    try:
        return WorkspaceActorRole(raw)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"invalid X-NF-Actor-Role: {x_nf_actor_role!r}",
        ) from exc


def _read_activation_state(
    org_id: uuid.UUID,
    ctx: OrgContext,
    db: Session,
) -> dict[str, Any]:
    _same_org(org_id, ctx)
    return build_activation_state_view(
        db,
        organization_id=ctx.org_id,
        is_demo=ctx.org_type == "demo",
        org_type=ctx.org_type,
    )


def _dispatch_activation(
    org_id: uuid.UUID,
    ctx: OrgContext,
    db: Session,
    body: GovernedActivationBody,
    actor_role: WorkspaceActorRole | None,
    actor_id: uuid.UUID | None,
) -> dict[str, Any]:
    _same_org(org_id, ctx)
    principal = resolve_activation_principal_for_governed_action(
        actor_role_from_header=actor_role,
        actor_id=actor_id,
    )
    try:
        result = dispatch_governed_activation_action(
            db,
            organization_id=ctx.org_id,
            is_demo=ctx.org_type == "demo",
            org_type=ctx.org_type,
            principal=principal,
            governed_action=body.governed_action,
            toggle=body.toggle,
            value=body.value,
            reason=body.reason,
            config_payload=body.config_payload,
        )
        db.commit()
        return result
    except GovernedActivationValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


def _verify_publish_gate(
    org_id: uuid.UUID,
    ctx: OrgContext,
    db: Session,
) -> dict[str, Any]:
    _same_org(org_id, ctx)
    row = activation_repo.get_or_create_activation_state(
        db,
        organization_id=ctx.org_id,
        is_demo=ctx.org_type == "demo",
    )
    live: dict[str, Any]
    auto: dict[str, Any]
    try:
        assert_live_publish_permitted(row)
        live = {"halted": False, "error": None}
    except ActivationPublishHaltedError as exc:
        live = {"halted": True, "error": str(exc)}
    try:
        assert_auto_publish_queue_permitted(row)
        auto = {"halted": False, "error": None}
    except ActivationPublishHaltedError as exc:
        auto = {"halted": True, "error": str(exc)}
    return {
        "schema_version": "nf_activation_verify_live_v1",
        "kill_switch_engaged": row.kill_switch_engaged,
        "live_publish_enabled": row.live_publish_enabled,
        "auto_publish_enabled": row.auto_publish_enabled,
        "live_publish_attempt": live,
        "auto_publish_queue_attempt": auto,
    }


@demo_activation_router.get("/{org_id}/operator/activation")
def demo_get_activation_state(
    org_id: uuid.UUID,
    ctx: Annotated[OrgContext, Depends(require_demo_org_db)],
    db: Annotated[Session, Depends(get_db_session)],
) -> dict[str, Any]:
    return _read_activation_state(org_id, ctx, db)


@real_activation_router.get("/{org_id}/operator/activation")
def real_get_activation_state(
    org_id: uuid.UUID,
    ctx: Annotated[OrgContext, Depends(require_real_org_db)],
    db: Annotated[Session, Depends(get_db_session)],
) -> dict[str, Any]:
    return _read_activation_state(org_id, ctx, db)


@demo_activation_router.post("/{org_id}/operator/activation/governed-action")
def demo_governed_activation_action(
    org_id: uuid.UUID,
    body: GovernedActivationBody,
    ctx: Annotated[OrgContext, Depends(require_demo_org_db)],
    db: Annotated[Session, Depends(get_db_session)],
    actor_role: Annotated[
        WorkspaceActorRole | None, Depends(_parse_actor_role_header)
    ] = None,
    actor_id: uuid.UUID | None = Query(default=None),
) -> dict[str, Any]:
    return _dispatch_activation(org_id, ctx, db, body, actor_role, actor_id)


@real_activation_router.post("/{org_id}/operator/activation/governed-action")
def real_governed_activation_action(
    org_id: uuid.UUID,
    body: GovernedActivationBody,
    ctx: Annotated[OrgContext, Depends(require_real_org_db)],
    db: Annotated[Session, Depends(get_db_session)],
    actor_role: Annotated[
        WorkspaceActorRole | None, Depends(_parse_actor_role_header)
    ] = None,
    actor_id: uuid.UUID | None = Query(default=None),
) -> dict[str, Any]:
    return _dispatch_activation(org_id, ctx, db, body, actor_role, actor_id)


@demo_activation_router.post("/{org_id}/operator/activation/verify-live")
def demo_verify_activation_live(
    org_id: uuid.UUID,
    ctx: Annotated[OrgContext, Depends(require_demo_org_db)],
    db: Annotated[Session, Depends(get_db_session)],
) -> dict[str, Any]:
    return _verify_publish_gate(org_id, ctx, db)


@real_activation_router.post("/{org_id}/operator/activation/verify-live")
def real_verify_activation_live(
    org_id: uuid.UUID,
    ctx: Annotated[OrgContext, Depends(require_real_org_db)],
    db: Annotated[Session, Depends(get_db_session)],
) -> dict[str, Any]:
    return _verify_publish_gate(org_id, ctx, db)
