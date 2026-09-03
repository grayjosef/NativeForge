"""Gate 139B: awarded grants, behind an authenticated organization context.

Gate 138 proved this lane round-trips at the repository. It had no routes, so
it was not customer-usable, and this is the part that makes it so.

## No update, and that is the audit model rather than an omission

```text
POST   .../awarded-grants                    create
GET    .../awarded-grants                    list, this organization only
GET    .../awarded-grants/{award_id}         read one
POST   .../awarded-grants/{award_id}/archive archive, with a reason
```

There is no PATCH. `awarded_grants_repository_service` has no update path and
says why:

> "There is no upsert. An award is a discrete event: a correction is a new row
> and the mistaken one is archived with `mistaken_award`, so the audit trail
> shows what was believed and when."

So a correction is archive-then-create, expressed as two calls the caller can
see, rather than a PATCH that would have to invent an UPDATE this table was
built to refuse.
"""

from __future__ import annotations

import uuid
from datetime import date
from typing import Annotated, Any

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from nativeforge.api.customer_org_context_dependency import require_demo_org_session
from nativeforge.api.deps_db import get_db_session
from nativeforge.api.org_context import OrgContext
from nativeforge.api.post_award_common import (
    accountable_identity,
    declared_fields,
    envelope,
    fixture_fields,
    refuse_caller_supplied,
    refuse_if_absent,
    refuse_if_blocked,
    same_org,
)
from nativeforge.services import awarded_grants_repository_service as repo

router = APIRouter(prefix="/v1/nf/demo/orgs", tags=["awarded-grants-demo"])


class AwardedGrantBody(BaseModel):
    """What a caller may say about an award.

    Every vocabulary field is the repository's, unvalidated here on purpose:
    restating `award_statuses` in a pydantic Enum would be a second copy that
    could drift from the CHECK constraint, which is the defect this campaign
    has found in six other shapes. The repository refuses an unrecognised
    value by name and that reason reaches the caller unchanged.
    """

    award_number: str = Field(min_length=1, max_length=255)
    award_title: str = Field(min_length=1, max_length=1024)
    funder_name: str = Field(min_length=1, max_length=512)
    program_name: str | None = Field(default=None, max_length=512)
    award_status: str = Field(min_length=1, max_length=64)
    award_amount: str | None = None
    award_currency: str | None = Field(default=None, max_length=8)
    period_start: date | None = None
    period_end: date | None = None
    awarded_at: date | None = None
    active_obligation_status: str | None = Field(default=None, max_length=64)
    requirements_extraction_status: str | None = Field(default=None, max_length=64)
    # `extra="allow"`, so `refuse_caller_supplied` can SEE a field a caller
    # should not set. Pydantic's default is to drop an unknown field silently,
    # which meant `is_demo: false` was ignored rather than refused - found by
    # this gate's own smoke invariant.
    model_config = {"extra": "allow"}


class ArchiveBody(BaseModel):
    award_status: str | None = Field(default=None, max_length=64)
    # `extra="allow"`, so `refuse_caller_supplied` can SEE a field a caller
    # should not set. Pydantic's default is to drop an unknown field silently,
    # which meant `is_demo: false` was ignored rather than refused - found by
    # this gate's own smoke invariant.
    model_config = {"extra": "allow"}


@router.post("/{org_id}/awarded-grants", status_code=status.HTTP_201_CREATED)
def create_awarded_grant(
    org_id: uuid.UUID,
    body: AwardedGrantBody,
    ctx: Annotated[OrgContext, Depends(require_demo_org_session)],
    db: Annotated[Session, Depends(get_db_session)],
) -> dict[str, Any]:
    same_org(org_id, ctx)
    refuse_caller_supplied(body)

    # Minted here, because `create_awarded_grant` does not return the id it
    # generated and a caller needs one to read the row back.
    award_id = uuid.uuid4()
    result = repo.create_awarded_grant(
        connection=db.connection(),
        award_id=award_id,
        organization_id=str(org_id),
        created_by_identity_id=accountable_identity(db, org_id),
        **declared_fields(body),
        **fixture_fields(),
    )
    refuse_if_blocked(result, wrote="awarded_grant")
    db.commit()
    return envelope(
        {
            "award_id": str(award_id),
            "organization_id": str(org_id),
            "award_status": result.get("award_status"),
            "rows_written": int(result["rows_written"]),
        }
    )


@router.get("/{org_id}/awarded-grants")
def list_awarded_grants(
    org_id: uuid.UUID,
    ctx: Annotated[OrgContext, Depends(require_demo_org_session)],
    db: Annotated[Session, Depends(get_db_session)],
    include_archived: bool = False,
) -> dict[str, Any]:
    same_org(org_id, ctx)
    result = repo.list_awarded_grants(
        connection=db.connection(),
        organization_id=str(org_id),
        include_archived=include_archived,
    )
    return envelope(
        {
            "organization_id": str(org_id),
            "rows_read": int(result.get("rows_read") or 0),
            "awards": list(result.get("awards") or result.get("rows") or []),
        }
    )


@router.get("/{org_id}/awarded-grants/{award_id}")
def get_awarded_grant(
    org_id: uuid.UUID,
    award_id: uuid.UUID,
    ctx: Annotated[OrgContext, Depends(require_demo_org_session)],
    db: Annotated[Session, Depends(get_db_session)],
) -> dict[str, Any]:
    same_org(org_id, ctx)
    result = repo.get_awarded_grant(
        connection=db.connection(),
        organization_id=str(org_id),
        award_id=str(award_id),
    )
    # A read anchored on this organization that found nothing is a 404,
    # whether the row belongs to another organization or does not exist.
    refuse_if_absent(result, what="awarded_grant")
    return envelope(
        {
            "award_id": str(award_id),
            "organization_id": str(org_id),
            "award_status": result.get("award_status"),
            "award_number": result.get("award_number"),
            "award_title": result.get("award_title"),
            "funder_name": result.get("funder_name"),
            "archived_at": result.get("archived_at"),
            "rows_read": int(result["rows_read"]),
        }
    )


@router.post("/{org_id}/awarded-grants/{award_id}/archive")
def archive_awarded_grant(
    org_id: uuid.UUID,
    award_id: uuid.UUID,
    body: ArchiveBody,
    ctx: Annotated[OrgContext, Depends(require_demo_org_session)],
    db: Annotated[Session, Depends(get_db_session)],
) -> dict[str, Any]:
    """The only lifecycle operation this table has.

    `award_status` is optional and is the correction's reason - `mistaken_award`
    is the one the repository documents. Setting it is not an update of the
    award's facts; it records why the row stopped being live.
    """
    same_org(org_id, ctx)
    result = repo.archive_awarded_grant(
        connection=db.connection(),
        organization_id=str(org_id),
        award_id=str(award_id),
        **declared_fields(body),
    )
    refuse_if_blocked(result, wrote="awarded_grant_archive")
    db.commit()
    return envelope(
        {
            "award_id": str(award_id),
            "organization_id": str(org_id),
            "archived": True,
            "rows_written": int(result["rows_written"]),
        },
        update_path_available=False,
        update_path_available_because=(
            "an award is a discrete event; a correction is a new row and the "
            "mistaken one is archived"
        ),
    )
