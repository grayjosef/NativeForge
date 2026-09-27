"""Who to contact, and where to submit.

Two reads and one extract, per plane. A new router rather than an addition to
`nofo_extraction_routes`, because that module is covered by gates whose
artifacts pin its shape, and there is no reason for a new capability to
disturb them.

The extract route reads the opportunity's stored notice text. It does not
fetch anything: the URL ingestion path has its own authorization rules and
this route is not a way around them.
"""

from __future__ import annotations

import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from nativeforge.api.customer_org_context_dependency import (
    require_demo_org_session,
    require_real_org_session,
)
from nativeforge.api.deps_db import get_db_session
from nativeforge.api.org_context import OrgContext
from nativeforge.api.tenant_guard import guard_same_org_403
from nativeforge.db.models import NfGrantSpark
from nativeforge.services import opportunity_apply_path_service as svc

demo_apply_router = APIRouter(prefix="/v1/nf/demo/orgs", tags=["apply-path-demo"])
real_apply_router = APIRouter(prefix="/v1/nf/real/orgs", tags=["apply-path-real"])


class CustomerContactBody(BaseModel):
    """A contact the customer already knows.

    No `provenance_kind`. The service stamps `customer_provided` and offers no
    way to say otherwise: a customer's own note about a program officer is
    theirs, and only a fact read from the official material could ever become
    something another organization sees.
    """

    role: str = Field(default="unknown", max_length=32)
    name: str | None = Field(default=None, max_length=256)
    title: str | None = Field(default=None, max_length=256)
    office: str | None = Field(default=None, max_length=512)
    email: str | None = Field(default=None, max_length=320)
    phone: str | None = Field(default=None, max_length=64)
    website: str | None = Field(default=None, max_length=2048)


def _spark_or_404(db: Session, org: OrgContext, spark_id: uuid.UUID) -> NfGrantSpark:
    spark = db.get(NfGrantSpark, spark_id)
    if spark is None or spark.organization_id != org.org_id:
        # One answer for "does not exist" and "belongs to somebody else". A
        # 403 here would confirm the opportunity exists, which is a fact about
        # another tenant.
        raise HTTPException(status_code=404, detail="opportunity not found")
    return spark


def _read(org_id: uuid.UUID, ctx: OrgContext, db: Session, spark_id: uuid.UUID) -> Any:
    guard_same_org_403(org_id, ctx)
    _spark_or_404(db, ctx, spark_id)
    return svc.read_apply_path(
        connection=db.connection(),
        organization_id=ctx.org_id,
        grant_spark_id=spark_id,
    )


def _extract(
    org_id: uuid.UUID, ctx: OrgContext, db: Session, spark_id: uuid.UUID
) -> Any:
    guard_same_org_403(org_id, ctx)
    spark = _spark_or_404(db, ctx, spark_id)

    text = spark.raw_nofo_text or ""
    if not text.strip():
        # Not an error. An opportunity whose notice has not been ingested is
        # the ordinary state of a newly tracked one, and saying "no contacts"
        # would be the absence-proves-absence mistake in a new place.
        return {
            "contacts_written": 0,
            "submission_written": 0,
            "submission_completeness": "unclear",
            "completeness_reasons": ["no_notice_text_available"],
            "text_complete": False,
            "notes": ["no_notice_text_available"],
        }

    result = svc.record_extraction(
        connection=db.connection(),
        organization_id=ctx.org_id,
        is_demo=ctx.org_type == "demo",
        grant_spark_id=spark_id,
        notice_text=text,
        # The stored notice text is what NativeForge holds, which is not the
        # same as the whole document. Claiming completeness here would let a
        # partial read produce a confident "this notice names nobody".
        text_complete=False,
        source_document=spark.raw_nofo_url or "stored notice text",
        source_url=spark.url,
    )
    db.commit()
    return result


@demo_apply_router.get("/{org_id}/grant-sparks/{spark_id}/apply-path")
def demo_read_apply_path(
    org_id: uuid.UUID,
    spark_id: uuid.UUID,
    ctx: Annotated[OrgContext, Depends(require_demo_org_session)],
    db: Annotated[Session, Depends(get_db_session)],
) -> dict[str, Any]:
    return _read(org_id, ctx, db, spark_id)


@demo_apply_router.post(
    "/{org_id}/grant-sparks/{spark_id}/apply-path/extract",
    status_code=status.HTTP_200_OK,
)
def demo_extract_apply_path(
    org_id: uuid.UUID,
    spark_id: uuid.UUID,
    ctx: Annotated[OrgContext, Depends(require_demo_org_session)],
    db: Annotated[Session, Depends(get_db_session)],
) -> dict[str, Any]:
    return _extract(org_id, ctx, db, spark_id)


@demo_apply_router.post(
    "/{org_id}/grant-sparks/{spark_id}/apply-path/contacts",
    status_code=status.HTTP_201_CREATED,
)
def demo_add_contact(
    org_id: uuid.UUID,
    spark_id: uuid.UUID,
    body: CustomerContactBody,
    ctx: Annotated[OrgContext, Depends(require_demo_org_session)],
    db: Annotated[Session, Depends(get_db_session)],
) -> dict[str, Any]:
    guard_same_org_403(org_id, ctx)
    _spark_or_404(db, ctx, spark_id)
    result = svc.add_customer_contact(
        connection=db.connection(),
        organization_id=ctx.org_id,
        is_demo=ctx.org_type == "demo",
        grant_spark_id=spark_id,
        **body.model_dump(),
    )
    if not result["written"]:
        raise HTTPException(status_code=422, detail=result)
    db.commit()
    return result


@real_apply_router.get("/{org_id}/grant-sparks/{spark_id}/apply-path")
def real_read_apply_path(
    org_id: uuid.UUID,
    spark_id: uuid.UUID,
    ctx: Annotated[OrgContext, Depends(require_real_org_session)],
    db: Annotated[Session, Depends(get_db_session)],
) -> dict[str, Any]:
    return _read(org_id, ctx, db, spark_id)


@real_apply_router.post(
    "/{org_id}/grant-sparks/{spark_id}/apply-path/extract",
    status_code=status.HTTP_200_OK,
)
def real_extract_apply_path(
    org_id: uuid.UUID,
    spark_id: uuid.UUID,
    ctx: Annotated[OrgContext, Depends(require_real_org_session)],
    db: Annotated[Session, Depends(get_db_session)],
) -> dict[str, Any]:
    return _extract(org_id, ctx, db, spark_id)


@real_apply_router.post(
    "/{org_id}/grant-sparks/{spark_id}/apply-path/contacts",
    status_code=status.HTTP_201_CREATED,
)
def real_add_contact(
    org_id: uuid.UUID,
    spark_id: uuid.UUID,
    body: CustomerContactBody,
    ctx: Annotated[OrgContext, Depends(require_real_org_session)],
    db: Annotated[Session, Depends(get_db_session)],
) -> dict[str, Any]:
    guard_same_org_403(org_id, ctx)
    _spark_or_404(db, ctx, spark_id)
    result = svc.add_customer_contact(
        connection=db.connection(),
        organization_id=ctx.org_id,
        is_demo=ctx.org_type == "demo",
        grant_spark_id=spark_id,
        **body.model_dump(),
    )
    if not result["written"]:
        raise HTTPException(status_code=422, detail=result)
    db.commit()
    return result
