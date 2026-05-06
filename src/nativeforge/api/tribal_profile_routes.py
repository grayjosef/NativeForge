"""Sprint 1 — tribal profile routes (DB-backed org context)."""

from __future__ import annotations

import uuid
from datetime import date
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from nativeforge.api.deps_db import (
    get_db_session,
    require_demo_org_db,
    require_real_org_db,
)
from nativeforge.api.org_context import OrgContext
from nativeforge.domain.enums import SamRegistrationStatus, TribalEntityType
from nativeforge.repositories import organizations as org_repo
from nativeforge.services import tribal_profile_service as tps
from nativeforge.services.tribal_profile_service import DuplicateTribalProfileError


class TribalProfileBody(BaseModel):
    legal_name: str = Field(min_length=1, max_length=512)
    entity_type: TribalEntityType
    uei: str | None = Field(default=None, max_length=32)
    ein: str | None = Field(default=None, max_length=32)
    sam_registration_status: SamRegistrationStatus = SamRegistrationStatus.unknown
    sam_expiration_date: date | None = None
    physical_address: dict[str, Any] | None = None
    mailing_address: dict[str, Any] | None = None
    service_area_description: str | None = Field(default=None, max_length=4096)
    authorized_representative: dict[str, Any] | None = None
    grants_manager: dict[str, Any] | None = None
    finance_contact: dict[str, Any] | None = None
    indirect_cost_rate: dict[str, Any] | None = None
    certifications: dict[str, Any] | None = None
    standard_narratives: dict[str, Any] | None = None
    attachment_index: list[Any] | dict[str, Any] | None = None


def _same_org(path_org: uuid.UUID, ctx: OrgContext) -> None:
    if path_org != ctx.org_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="path org_id does not match authenticated org",
        )


def _body_to_payload(body: TribalProfileBody) -> tps.TribalProfilePayload:
    return tps.TribalProfilePayload(
        legal_name=body.legal_name,
        entity_type=body.entity_type,
        uei=body.uei,
        ein=body.ein,
        sam_registration_status=body.sam_registration_status,
        sam_expiration_date=body.sam_expiration_date,
        physical_address=body.physical_address,
        mailing_address=body.mailing_address,
        service_area_description=body.service_area_description,
        authorized_representative=body.authorized_representative,
        grants_manager=body.grants_manager,
        finance_contact=body.finance_contact,
        indirect_cost_rate=body.indirect_cost_rate,
        certifications=body.certifications,
        standard_narratives=body.standard_narratives,
        attachment_index=body.attachment_index,
    )


demo_profile_router = APIRouter(prefix="/v1/nf/demo/orgs", tags=["tribal-profile-demo"])
real_profile_router = APIRouter(prefix="/v1/nf/real/orgs", tags=["tribal-profile-real"])


@demo_profile_router.post(
    "/{org_id}/tribal-profile",
    status_code=status.HTTP_201_CREATED,
)
def demo_create_profile(
    org_id: uuid.UUID,
    ctx: Annotated[OrgContext, Depends(require_demo_org_db)],
    db: Annotated[Session, Depends(get_db_session)],
    body: TribalProfileBody,
    actor_id: uuid.UUID | None = None,
) -> dict[str, Any]:
    _same_org(org_id, ctx)
    org = org_repo.get_organization(db, org_id)
    if org is None:
        raise HTTPException(status_code=404, detail="organization not found")
    try:
        row = tps.create_tribal_profile(
            db, org=org, body=_body_to_payload(body), actor_id=actor_id
        )
        db.commit()
        db.refresh(row)
    except DuplicateTribalProfileError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="tribal profile already exists for this organization",
        ) from None
    return tps.profile_to_dict(row)


@demo_profile_router.get("/{org_id}/tribal-profile")
def demo_get_profile(
    org_id: uuid.UUID,
    ctx: Annotated[OrgContext, Depends(require_demo_org_db)],
    db: Annotated[Session, Depends(get_db_session)],
) -> dict[str, Any]:
    _same_org(org_id, ctx)
    row = tps.get_tribal_profile(db, org_id=ctx.org_id, org_type=ctx.org_type)
    if row is None:
        raise HTTPException(status_code=404, detail="tribal profile not found")
    return tps.profile_to_dict(row)


@demo_profile_router.put("/{org_id}/tribal-profile")
def demo_put_profile(
    org_id: uuid.UUID,
    ctx: Annotated[OrgContext, Depends(require_demo_org_db)],
    db: Annotated[Session, Depends(get_db_session)],
    body: TribalProfileBody,
    actor_id: uuid.UUID | None = None,
) -> dict[str, Any]:
    _same_org(org_id, ctx)
    row = tps.update_tribal_profile(
        db,
        org_id=ctx.org_id,
        org_type=ctx.org_type,
        body=_body_to_payload(body),
        actor_id=actor_id,
    )
    if row is None:
        raise HTTPException(status_code=404, detail="tribal profile not found")
    db.commit()
    db.refresh(row)
    return tps.profile_to_dict(row)


@demo_profile_router.get("/{org_id}/tribal-profile/export")
def demo_export_profile(
    org_id: uuid.UUID,
    ctx: Annotated[OrgContext, Depends(require_demo_org_db)],
    db: Annotated[Session, Depends(get_db_session)],
    actor_id: uuid.UUID | None = None,
) -> dict[str, Any]:
    _same_org(org_id, ctx)
    out = tps.export_tribal_profile(
        db, org_id=ctx.org_id, org_type=ctx.org_type, actor_id=actor_id
    )
    if out is None:
        raise HTTPException(status_code=404, detail="tribal profile not found")
    db.commit()
    return out


@real_profile_router.post(
    "/{org_id}/tribal-profile",
    status_code=status.HTTP_201_CREATED,
)
def real_create_profile(
    org_id: uuid.UUID,
    ctx: Annotated[OrgContext, Depends(require_real_org_db)],
    db: Annotated[Session, Depends(get_db_session)],
    body: TribalProfileBody,
    actor_id: uuid.UUID | None = None,
) -> dict[str, Any]:
    _same_org(org_id, ctx)
    org = org_repo.get_organization(db, org_id)
    if org is None:
        raise HTTPException(status_code=404, detail="organization not found")
    try:
        row = tps.create_tribal_profile(
            db, org=org, body=_body_to_payload(body), actor_id=actor_id
        )
        db.commit()
        db.refresh(row)
    except DuplicateTribalProfileError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="tribal profile already exists for this organization",
        ) from None
    return tps.profile_to_dict(row)


@real_profile_router.get("/{org_id}/tribal-profile")
def real_get_profile(
    org_id: uuid.UUID,
    ctx: Annotated[OrgContext, Depends(require_real_org_db)],
    db: Annotated[Session, Depends(get_db_session)],
) -> dict[str, Any]:
    _same_org(org_id, ctx)
    row = tps.get_tribal_profile(db, org_id=ctx.org_id, org_type=ctx.org_type)
    if row is None:
        raise HTTPException(status_code=404, detail="tribal profile not found")
    return tps.profile_to_dict(row)


@real_profile_router.put("/{org_id}/tribal-profile")
def real_put_profile(
    org_id: uuid.UUID,
    ctx: Annotated[OrgContext, Depends(require_real_org_db)],
    db: Annotated[Session, Depends(get_db_session)],
    body: TribalProfileBody,
    actor_id: uuid.UUID | None = None,
) -> dict[str, Any]:
    _same_org(org_id, ctx)
    row = tps.update_tribal_profile(
        db,
        org_id=ctx.org_id,
        org_type=ctx.org_type,
        body=_body_to_payload(body),
        actor_id=actor_id,
    )
    if row is None:
        raise HTTPException(status_code=404, detail="tribal profile not found")
    db.commit()
    db.refresh(row)
    return tps.profile_to_dict(row)


@real_profile_router.get("/{org_id}/tribal-profile/export")
def real_export_profile(
    org_id: uuid.UUID,
    ctx: Annotated[OrgContext, Depends(require_real_org_db)],
    db: Annotated[Session, Depends(get_db_session)],
    actor_id: uuid.UUID | None = None,
) -> dict[str, Any]:
    _same_org(org_id, ctx)
    out = tps.export_tribal_profile(
        db, org_id=ctx.org_id, org_type=ctx.org_type, actor_id=actor_id
    )
    if out is None:
        raise HTTPException(status_code=404, detail="tribal profile not found")
    db.commit()
    return out
