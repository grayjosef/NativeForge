"""DB session + org context from `organizations` and dev headers (Sprint 0)."""

from __future__ import annotations

import uuid
from collections.abc import Generator
from typing import Annotated

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from nativeforge.api.org_context import OrgContext
from nativeforge.db.rls import apply_org_rls_gucs
from nativeforge.db.session import SessionLocal
from nativeforge.lib.demo_isolation import OrgType
from nativeforge.lib.settings import get_settings
from nativeforge.repositories import organizations as org_repo


def get_db_session() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


async def get_org_context_with_db(
    db: Annotated[Session, Depends(get_db_session)],
    x_nf_org_id: str | None = Header(default=None, alias="X-NF-Org-Id"),
) -> OrgContext:
    """
    Resolve org type from persisted `organizations` row (source of truth for Sprint 0+).

    Requires `X-NF-Org-Id` and NF_DEV_ORG_HEADERS=true
    (same contract as NF-001 smoke routes).
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

    org = org_repo.get_organization(db, oid)
    if org is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="organization not found",
        )

    ot: OrgType = "demo" if org.org_type == "demo" else "real"
    apply_org_rls_gucs(db, oid, ot)
    return OrgContext(org_id=oid, org_type=ot)


def require_demo_org_db(
    ctx: Annotated[OrgContext, Depends(get_org_context_with_db)],
) -> OrgContext:
    if ctx.org_type != "demo":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="demo-only route requires a demo organization",
        )
    return ctx


def require_real_org_db(
    ctx: Annotated[OrgContext, Depends(get_org_context_with_db)],
) -> OrgContext:
    if ctx.org_type != "real":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="real-data route requires a real organization",
        )
    return ctx
