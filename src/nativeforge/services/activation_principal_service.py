"""M8: operator console principal (role header + actor id)."""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from fastapi import Header, HTTPException, status

from nativeforge.domain.enums import WorkspaceActorRole
from nativeforge.lib.settings import get_settings


class AgentGovernedActionDeniedError(PermissionError):
    """Raised when an agent attempts a governed operator action."""


class OperatorRoleRequiredError(PermissionError):
    """Raised when principal role is missing or not operator/admin."""


@dataclass(frozen=True, slots=True)
class ActivationPrincipal:
    actor_id: uuid.UUID | None
    actor_role: WorkspaceActorRole


def parse_actor_role_header(
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


def require_operator_principal(
    *,
    actor_role: WorkspaceActorRole | None,
    actor_id: uuid.UUID | None,
) -> ActivationPrincipal:
    if actor_role is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="X-NF-Actor-Role required (operator or admin)",
        )
    if actor_role == WorkspaceActorRole.agent:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="agents are denied governed activation actions",
        )
    return ActivationPrincipal(actor_id=actor_id, actor_role=actor_role)


def resolve_activation_principal_for_governed_action(
    *,
    actor_role_from_header: WorkspaceActorRole | None,
    actor_id: uuid.UUID | None,
) -> ActivationPrincipal:
    """Honor X-NF-Actor-Role only in dev-header mode; never in production-shaped config."""
    settings = get_settings()
    if not settings.nf_dev_org_headers:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "activation governed actions require authenticated identity; "
                "X-NF-Actor-Role is not honored when NF_DEV_ORG_HEADERS=false"
            ),
        )
    return require_operator_principal(
        actor_role=actor_role_from_header,
        actor_id=actor_id,
    )


def assert_governed_action_permitted(
    *,
    principal: ActivationPrincipal,
    governed_action: str,
) -> None:
    if principal.actor_role == WorkspaceActorRole.agent:
        raise AgentGovernedActionDeniedError(
            f"agent denied governed action {governed_action!r}"
        )
    if principal.actor_role not in (
        WorkspaceActorRole.operator,
        WorkspaceActorRole.admin,
    ):
        raise OperatorRoleRequiredError(
            f"operator or admin required for {governed_action!r}"
        )
