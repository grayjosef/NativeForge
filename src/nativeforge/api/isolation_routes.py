"""Minimal routes proving Layer 3 demo vs real separation (NF-001)."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from nativeforge.api.isolation_deps import require_demo_org, require_real_org
from nativeforge.api.org_context import OrgContext

router = APIRouter(prefix="/v1/isolation", tags=["demo-isolation"])


@router.get("/demo-only")
def demo_only_ping(
    org: Annotated[OrgContext, Depends(require_demo_org)],
) -> dict[str, str]:
    return {"scope": "demo", "org_id": str(org.org_id)}


@router.get("/real-only")
def real_only_ping(
    org: Annotated[OrgContext, Depends(require_real_org)],
) -> dict[str, str]:
    return {"scope": "real", "org_id": str(org.org_id)}
