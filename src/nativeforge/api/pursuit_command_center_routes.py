"""Individual pursuit command center: derived workflow and funder memory.

Reads assemble existing records. The only write is a tenant-scoped
interaction. Nothing here fetches a notice or starts a collector.
"""

from __future__ import annotations

import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from nativeforge.api.customer_org_context_dependency import (
    require_demo_org_session,
    require_real_org_session,
)
from nativeforge.api.deps_db import get_db_session
from nativeforge.api.org_context import OrgContext
from nativeforge.api.tenant_guard import guard_same_org_403
from nativeforge.db.models import NfGrantPursuit, NfGrantSpark
from nativeforge.services import funder_interaction_service as ixn
from nativeforge.services.pursuit_command_center_service import assemble_command_center

demo_command_router = APIRouter(
    prefix="/v1/nf/demo/orgs", tags=["pursuit-command-center-demo"]
)
real_command_router = APIRouter(
    prefix="/v1/nf/real/orgs", tags=["pursuit-command-center-real"]
)


class InteractionBody(BaseModel):
    interaction_type: str = Field(max_length=32)
    status: str = Field(default="open", max_length=32)
    occurred_at: str | None = None
    follow_up_at: str | None = None
    subject: str | None = Field(default=None, max_length=512)
    notes: str | None = None
    evidence_ref: str | None = Field(default=None, max_length=512)
    owner_label: str | None = Field(default=None, max_length=256)
    contact_id: uuid.UUID | None = None


def _spark_or_404(db: Session, org: OrgContext, spark_id: uuid.UUID) -> NfGrantSpark:
    spark = db.get(NfGrantSpark, spark_id)
    if spark is None or spark.organization_id != org.org_id:
        raise HTTPException(status_code=404, detail="opportunity not found")
    return spark


def _read(org_id: uuid.UUID, ctx: OrgContext, db: Session, spark_id: uuid.UUID) -> Any:
    guard_same_org_403(org_id, ctx)
    _spark_or_404(db, ctx, spark_id)
    body = assemble_command_center(
        session=db, organization_id=ctx.org_id, grant_spark_id=spark_id
    )
    if body is None:
        raise HTTPException(status_code=404, detail="opportunity not found")
    return body


def _write_interaction(
    org_id: uuid.UUID,
    ctx: OrgContext,
    db: Session,
    spark_id: uuid.UUID,
    body: InteractionBody,
) -> Any:
    guard_same_org_403(org_id, ctx)
    spark = _spark_or_404(db, ctx, spark_id)
    pursuit = db.scalar(
        select(NfGrantPursuit).where(
            NfGrantPursuit.organization_id == ctx.org_id,
            NfGrantPursuit.grant_spark_id == spark_id,
        )
    )
    result = ixn.record_interaction(
        connection=db.connection(),
        organization_id=ctx.org_id,
        is_demo=ctx.org_type == "demo",
        grant_spark_id=spark_id,
        grant_pursuit_id=pursuit.id if pursuit else None,
        contact_id=body.contact_id,
        funder_agency=spark.agency,
        program_name=spark.program_name,
        interaction_type=body.interaction_type,
        status=body.status,
        occurred_at=body.occurred_at,
        follow_up_at=body.follow_up_at,
        subject=body.subject,
        notes=body.notes,
        evidence_ref=body.evidence_ref,
        owner_label=body.owner_label,
    )
    if not result["written"]:
        raise HTTPException(status_code=422, detail=result)
    db.commit()
    return assemble_command_center(
        session=db, organization_id=ctx.org_id, grant_spark_id=spark_id
    )


@demo_command_router.get("/{org_id}/grant-sparks/{spark_id}/command-center")
def demo_read(
    org_id: uuid.UUID,
    spark_id: uuid.UUID,
    ctx: Annotated[OrgContext, Depends(require_demo_org_session)],
    db: Annotated[Session, Depends(get_db_session)],
) -> dict[str, Any]:
    return _read(org_id, ctx, db, spark_id)


@demo_command_router.post(
    "/{org_id}/grant-sparks/{spark_id}/interactions",
    status_code=status.HTTP_201_CREATED,
)
def demo_write(
    org_id: uuid.UUID,
    spark_id: uuid.UUID,
    body: InteractionBody,
    ctx: Annotated[OrgContext, Depends(require_demo_org_session)],
    db: Annotated[Session, Depends(get_db_session)],
) -> dict[str, Any]:
    return _write_interaction(org_id, ctx, db, spark_id, body)


@real_command_router.get("/{org_id}/grant-sparks/{spark_id}/command-center")
def real_read(
    org_id: uuid.UUID,
    spark_id: uuid.UUID,
    ctx: Annotated[OrgContext, Depends(require_real_org_session)],
    db: Annotated[Session, Depends(get_db_session)],
) -> dict[str, Any]:
    return _read(org_id, ctx, db, spark_id)


@real_command_router.post(
    "/{org_id}/grant-sparks/{spark_id}/interactions",
    status_code=status.HTTP_201_CREATED,
)
def real_write(
    org_id: uuid.UUID,
    spark_id: uuid.UUID,
    body: InteractionBody,
    ctx: Annotated[OrgContext, Depends(require_real_org_session)],
    db: Annotated[Session, Depends(get_db_session)],
) -> dict[str, Any]:
    return _write_interaction(org_id, ctx, db, spark_id, body)
