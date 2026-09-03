"""Gate 139C: award requirements, attached to an award in the same organization.

## The two things this route will not do

**It will not invent a requirement.** `requirement_source` is the caller's, and
the vocabulary already distinguishes where a requirement came from:

```text
human_entered            a person typed it
evidence_extracted       something read it out of a document
projected_from_nofo      derived from the notice, and labelled as derived
needs_human_review       something tried and could not be sure
unsupported_document_type  the document could not be read at all
unknown
```

A route that defaulted this to `evidence_extracted` would be claiming an
extraction happened. It defaults to nothing: the caller says, or the repository
refuses.

**It will not infer a deadline.** `requirement_due_date` is accepted only
alongside a `due_date_status` the caller also supplies, and the status
vocabulary is what makes an unsure date sayable:

```text
verified | calculated | estimated | needs_human_review | unsupported | unknown
```

Nothing here reads a title or a description and produces a date.
`award_requirements_repository_service.prohibited_inferences()` names what may
not be derived and this route adds no exception to it.

## Attachment is same-organization, twice over

The requirement's `awarded_grant_id` must name an award **this organization
owns**. That is checked by reading the award through the anchored read before
the write — not by trusting the id. `awarded_grant_id` is in the repository's
`FORBIDDEN_ANCHOR_NAMES`: it is a relationship, never the authority.
"""

from __future__ import annotations

import uuid
from datetime import date
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, model_validator
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
from nativeforge.services import award_requirements_repository_service as repo
from nativeforge.services import awarded_grants_repository_service as award_repo

router = APIRouter(prefix="/v1/nf/demo/orgs", tags=["award-requirements-demo"])

#: A due date with no status is a date nobody vouched for.
DUE_DATE_WITHOUT_STATUS = "due_date_supplied_without_a_due_date_status"

#: What an unsupported or unread requirement stays.
UNRESOLVED_STATUSES: tuple[str, ...] = ("unknown", "needs_human_review")


class RequirementBody(BaseModel):
    requirement_type: str = Field(min_length=1, max_length=64)
    requirement_title: str = Field(min_length=1, max_length=1024)
    requirement_description: str | None = Field(default=None, max_length=8192)
    requirement_status: str = Field(min_length=1, max_length=64)
    requirement_source: str = Field(min_length=1, max_length=64)
    requirement_source_ref: str | None = Field(default=None, max_length=512)
    requirement_due_date: date | None = None
    due_date_status: str | None = Field(default=None, max_length=64)
    recurrence_rule: str | None = Field(default=None, max_length=64)
    proof_required: bool = False
    proof_status: str | None = Field(default=None, max_length=64)
    submission_status: str | None = Field(default=None, max_length=64)

    @model_validator(mode="after")
    def _a_date_needs_somebody_to_vouch_for_it(self) -> RequirementBody:
        """A due date arrives with a status or it does not arrive.

        The status vocabulary exists so an unsure date can be stored as unsure.
        Accepting a bare date would make every date look `verified` to a reader,
        which is the fabrication this gate is forbidden from.
        """
        if self.requirement_due_date is not None and not self.due_date_status:
            raise ValueError(DUE_DATE_WITHOUT_STATUS)
        return self

    # `extra="allow"`, so `refuse_caller_supplied` can SEE a field a caller
    # should not set. Pydantic's default is to drop an unknown field silently,
    # which meant `is_demo: false` was ignored rather than refused - found by
    # this gate's own smoke invariant.
    model_config = {"extra": "allow"}


class ArchiveBody(BaseModel):
    requirement_status: str | None = Field(default=None, max_length=64)
    # `extra="allow"`, so `refuse_caller_supplied` can SEE a field a caller
    # should not set. Pydantic's default is to drop an unknown field silently,
    # which meant `is_demo: false` was ignored rather than refused - found by
    # this gate's own smoke invariant.
    model_config = {"extra": "allow"}


def _award_in_this_org(db: Session, org_id: uuid.UUID, award_id: uuid.UUID) -> None:
    """The award must be one this organization owns.

    Read through the anchored read, so an award in another organization is
    simply not found - the id is never trusted on its own.
    """
    found = award_repo.get_awarded_grant(
        connection=db.connection(),
        organization_id=str(org_id),
        award_id=str(award_id),
    )
    if not found.get("rows_read"):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": "awarded_grant_not_found_in_this_organization",
                "awarded_grant_id": str(award_id),
            },
        )


@router.post(
    "/{org_id}/awarded-grants/{award_id}/requirements",
    status_code=status.HTTP_201_CREATED,
)
def create_requirement(
    org_id: uuid.UUID,
    award_id: uuid.UUID,
    body: RequirementBody,
    ctx: Annotated[OrgContext, Depends(require_demo_org_session)],
    db: Annotated[Session, Depends(get_db_session)],
) -> dict[str, Any]:
    same_org(org_id, ctx)
    refuse_caller_supplied(body)
    _award_in_this_org(db, org_id, award_id)

    requirement_id = uuid.uuid4()
    result = repo.create_award_requirement(
        connection=db.connection(),
        requirement_id=requirement_id,
        organization_id=str(org_id),
        awarded_grant_id=str(award_id),
        created_by_identity_id=accountable_identity(db, org_id),
        **declared_fields(body),
        **fixture_fields(),
    )
    refuse_if_blocked(result, wrote="award_requirement")
    db.commit()
    return envelope(
        {
            "requirement_id": str(requirement_id),
            "awarded_grant_id": str(award_id),
            "organization_id": str(org_id),
            "requirement_status": result.get("requirement_status"),
            "requirement_source": result.get("requirement_source"),
            "due_date_status": result.get("due_date_status"),
            "rows_written": int(result["rows_written"]),
        },
        due_date_inferred=False,
        requirement_extracted_by_this_route=False,
    )


@router.get("/{org_id}/awarded-grants/{award_id}/requirements")
def list_requirements(
    org_id: uuid.UUID,
    award_id: uuid.UUID,
    ctx: Annotated[OrgContext, Depends(require_demo_org_session)],
    db: Annotated[Session, Depends(get_db_session)],
    include_archived: bool = False,
) -> dict[str, Any]:
    same_org(org_id, ctx)
    result = repo.list_requirements_for_award(
        connection=db.connection(),
        organization_id=str(org_id),
        awarded_grant_id=str(award_id),
        include_archived=include_archived,
    )
    return envelope(
        {
            "organization_id": str(org_id),
            "awarded_grant_id": str(award_id),
            "rows_read": int(result.get("rows_read") or 0),
            "requirements": list(result.get("requirements") or []),
        }
    )


@router.get("/{org_id}/requirements/{requirement_id}")
def get_requirement(
    org_id: uuid.UUID,
    requirement_id: uuid.UUID,
    ctx: Annotated[OrgContext, Depends(require_demo_org_session)],
    db: Annotated[Session, Depends(get_db_session)],
) -> dict[str, Any]:
    same_org(org_id, ctx)
    result = repo.get_award_requirement(
        connection=db.connection(),
        organization_id=str(org_id),
        requirement_id=str(requirement_id),
    )
    refuse_if_absent(result, what="award_requirement")
    return envelope(
        {
            "requirement_id": str(requirement_id),
            "organization_id": str(org_id),
            "requirement_status": result.get("requirement_status"),
            "requirement_source": result.get("requirement_source"),
            "requirement_due_date": result.get("requirement_due_date"),
            "due_date_status": result.get("due_date_status"),
            "unresolved": result.get("requirement_status") in UNRESOLVED_STATUSES,
            "rows_read": int(result["rows_read"]),
        }
    )


@router.post("/{org_id}/requirements/{requirement_id}/archive")
def archive_requirement(
    org_id: uuid.UUID,
    requirement_id: uuid.UUID,
    body: ArchiveBody,
    ctx: Annotated[OrgContext, Depends(require_demo_org_session)],
    db: Annotated[Session, Depends(get_db_session)],
) -> dict[str, Any]:
    """Archive, because there is no update.

    A requirement whose status changed is a new row: a compliance calendar is a
    list of dated obligations and overwriting last quarter's row erases whether
    last quarter was met. The repository says exactly that.
    """
    same_org(org_id, ctx)
    result = repo.archive_award_requirement(
        connection=db.connection(),
        organization_id=str(org_id),
        requirement_id=str(requirement_id),
        **declared_fields(body),
    )
    refuse_if_blocked(result, wrote="award_requirement_archive")
    db.commit()
    return envelope(
        {
            "requirement_id": str(requirement_id),
            "organization_id": str(org_id),
            "archived": True,
            "rows_written": int(result["rows_written"]),
        },
        update_path_available=False,
        update_path_available_because=(
            "a recurring obligation is many rows, one per period; overwriting "
            "last quarter's row erases whether last quarter was met"
        ),
    )
