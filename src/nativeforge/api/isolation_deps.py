"""
Development-only dependencies to simulate org context for demo isolation tests.

Production must replace this with JWT + organizations.org_type lookup.
When `NF_DEV_ORG_HEADERS=false`, routes using these dependencies return 503.
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import Depends, Header, HTTPException, status

from nativeforge.api.org_context import OrgContext
from nativeforge.lib.demo_isolation import org_type_for
from nativeforge.lib.settings import demo_org_uuid_set, get_settings


async def get_org_context_dev(
    x_nf_org_id: str | None = Header(default=None, alias="X-NF-Org-Id"),
) -> OrgContext:
    """
    Resolve org type from `NF_DEMO_ORG_IDS` allowlist only (single header).

    Spoofing `org_type` via a second header is intentionally not supported —
    the allowlist is the source of truth for NF-001.
    """
    settings = get_settings()
    if not settings.nf_dev_org_headers:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="org context headers disabled (NF_DEV_ORG_HEADERS=false)",
        )
    if not x_nf_org_id or not str(x_nf_org_id).strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="missing X-NF-Org-Id",
        )
    try:
        oid = uuid.UUID(str(x_nf_org_id).strip())
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="invalid X-NF-Org-Id",
        ) from e

    demo_ids = demo_org_uuid_set(settings)
    ot = org_type_for(oid, demo_ids)
    return OrgContext(org_id=oid, org_type=ot)


def require_demo_org(
    ctx: Annotated[OrgContext, Depends(get_org_context_dev)],
) -> OrgContext:
    if ctx.org_type != "demo":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="demo-only route requires a demo organization",
        )
    return ctx


def require_real_org(
    ctx: Annotated[OrgContext, Depends(get_org_context_dev)],
) -> OrgContext:
    if ctx.org_type != "real":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="real-data route requires a real (non-demo) organization",
        )
    return ctx
