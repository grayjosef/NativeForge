"""Single tenant-enforcement point for API handlers (Gate 58).

Before this module, ``_same_org`` was copy-pasted into 14 route modules. Two
consequences of that, both real:

  * there was no single place to add audit-on-denial, and
  * the copies had already drifted — eleven raised
    ``403 path org_id does not match authenticated org`` while three raised
    ``404 organization not found``.

This module keeps **both** existing response shapes verbatim, because tests and
clients depend on them, and routes the decision through
``api_enforcement_service`` so every denial produces a modeled audit event from
one code path.

Behaviour is deliberately unchanged: same status codes, same detail strings.
What changes is that there is now one implementation instead of fourteen.

Audit events are modeled, not stored (``persisted: false``). Customer
persistence is not live.
"""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import HTTPException, status

from nativeforge.api.org_context import OrgContext
from nativeforge.services.api_enforcement_service import (
    build_request_enforcement_context,
    enforce_tenant_access,
)

# Denials recorded in-process for assertions and operator inspection. This is a
# bounded ring buffer, NOT an audit log and NOT persistence.
_RECENT_DENIALS: list[dict[str, Any]] = []
_MAX_RECENT_DENIALS = 200


def recent_denials() -> list[dict[str, Any]]:
    """Read the in-process denial ring buffer (tests / operator inspection)."""
    return list(_RECENT_DENIALS)


def reset_recent_denials() -> None:
    _RECENT_DENIALS.clear()


def _record(decision: dict[str, Any]) -> None:
    for ev in decision.get("audit_events") or []:
        _RECENT_DENIALS.append(ev)
    while len(_RECENT_DENIALS) > _MAX_RECENT_DENIALS:
        _RECENT_DENIALS.pop(0)


def evaluate_same_org(
    path_org: uuid.UUID,
    ctx: OrgContext,
    *,
    object_type: str = "workspace",
    action: str = "access",
    actor_id: str | None = None,
) -> dict[str, Any]:
    """Evaluate org-scoped access and record any denial. Never raises."""
    context = build_request_enforcement_context(
        requesting_org_id=str(ctx.org_id),
        actor_id=actor_id or str(ctx.org_id),
        plane=getattr(ctx, "org_type", "unknown") or "unknown",
    )
    decision = enforce_tenant_access(
        context=context,
        resource_org_id=str(path_org),
        object_type=object_type,
        action=action,
    )
    if not decision.get("allowed"):
        _record(decision)
    return decision


def guard_same_org_403(
    path_org: uuid.UUID,
    ctx: OrgContext,
    *,
    object_type: str = "workspace",
    action: str = "access",
) -> None:
    """Tenant guard preserving the 403 response used by most route modules."""
    decision = evaluate_same_org(
        path_org, ctx, object_type=object_type, action=action
    )
    if not decision.get("allowed"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="path org_id does not match authenticated org",
        )


def guard_same_org_404(
    path_org: uuid.UUID,
    ctx: OrgContext,
    *,
    object_type: str = "workspace",
    action: str = "access",
) -> None:
    """Tenant guard preserving the 404 response used by three route modules.

    404 avoids confirming that another organization exists. It is kept as-is
    rather than unified to 403, because callers and tests depend on it and
    changing an API response is not in scope for this gate.
    """
    decision = evaluate_same_org(
        path_org, ctx, object_type=object_type, action=action
    )
    if not decision.get("allowed"):
        raise HTTPException(status_code=404, detail="organization not found")
