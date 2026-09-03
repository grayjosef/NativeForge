"""Gate 139D: proof and audit events, attached to a requirement in the same org.

## Immutable, and the contract says so

```text
POST   .../requirements/{id}/proof-events            append
GET    .../requirements/{id}/proof-events            list
GET    .../proof-events/{event_id}                   read one
POST   .../proof-events/{event_id}/supersede         a later event replaces it
POST   .../proof-events/{event_id}/archive           archive
```

There is no update, and this is the strongest version of that rule in the
codebase:

> "There is no upsert and no update of an event's own facts. What was believed
> at the time is what the row says, forever."

So a correction is a **supersede**: a new event that names the one it replaces,
with the old row's `superseded_at` set. `supersede_proof_event` is the only
post-insert path and `POST_INSERT_WRITABLE_COLUMNS` is
`("superseded_at", "archived_at")` — two columns, both lifecycle, neither a
fact about what happened.

## No document is required, and none is stored

`proof_document_ref` is a reference a caller may supply. No body is read,
no store is contacted, and `proof_document_storage_available` stays false:
Gate 96's `detect_body_store_mode()` reports `unconfigured` and nothing here
overrides it.

## No fake submission proof

`proof_source` is the caller's, from the same vocabulary the requirements lane
uses. Nothing here defaults it to `evidence_extracted`, which would be claiming
something read a document.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status
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
    refuse_body_storage,
    refuse_caller_supplied,
    refuse_if_absent,
    refuse_if_blocked,
    same_org,
)
from nativeforge.services import (
    award_requirement_proof_audit_repository_service as repo,
)
from nativeforge.services import award_requirements_repository_service as req_repo

router = APIRouter(prefix="/v1/nf/demo/orgs", tags=["award-proof-events-demo"])


class ProofEventBody(BaseModel):
    event_type: str = Field(min_length=1, max_length=64)
    event_status: str = Field(min_length=1, max_length=64)
    proof_summary: str | None = Field(default=None, max_length=8192)
    proof_source: str = Field(min_length=1, max_length=64)
    proof_source_ref: str | None = Field(default=None, max_length=512)
    proof_document_ref: str | None = Field(default=None, max_length=512)
    submitted_at: datetime | None = None
    accepted_at: datetime | None = None
    rejected_at: datetime | None = None
    reviewed_at: datetime | None = None
    # `extra="allow"`, so `refuse_caller_supplied` can SEE a field a caller
    # should not set. Pydantic's default is to drop an unknown field silently,
    # which meant `is_demo: false` was ignored rather than refused - found by
    # this gate's own smoke invariant.
    model_config = {"extra": "allow"}


class SupersedeBody(BaseModel):
    """A correction is a new event that names the one it replaces.

    No `event_type`. `supersede_proof_event` sets `proof_superseded` itself and
    raised `TypeError: got multiple values for keyword argument 'event_type'`
    when the route passed one - the repository names the type because a
    supersede IS a supersede, and letting a caller call it something else would
    make the trail unreadable.
    """

    event_status: str = Field(min_length=1, max_length=64)
    proof_summary: str | None = Field(default=None, max_length=8192)
    proof_source: str = Field(min_length=1, max_length=64)
    proof_source_ref: str | None = Field(default=None, max_length=512)
    proof_document_ref: str | None = Field(default=None, max_length=512)
    submitted_at: datetime | None = None
    accepted_at: datetime | None = None
    rejected_at: datetime | None = None
    reviewed_at: datetime | None = None

    model_config = {"extra": "allow"}


def _requirement_in_this_org(
    db: Session, org_id: uuid.UUID, requirement_id: uuid.UUID
) -> dict[str, Any]:
    found = req_repo.get_award_requirement(
        connection=db.connection(),
        organization_id=str(org_id),
        requirement_id=str(requirement_id),
    )
    if not found.get("rows_read"):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": "award_requirement_not_found_in_this_organization",
                "award_requirement_id": str(requirement_id),
            },
        )
    return found


@router.post(
    "/{org_id}/requirements/{requirement_id}/proof-events",
    status_code=status.HTTP_201_CREATED,
)
def create_proof_event(
    org_id: uuid.UUID,
    requirement_id: uuid.UUID,
    body: ProofEventBody,
    ctx: Annotated[OrgContext, Depends(require_demo_org_session)],
    db: Annotated[Session, Depends(get_db_session)],
) -> dict[str, Any]:
    same_org(org_id, ctx)
    refuse_caller_supplied(body)
    refuse_body_storage(body)
    requirement = _requirement_in_this_org(db, org_id, requirement_id)

    event_id = uuid.uuid4()
    result = repo.create_proof_event(
        connection=db.connection(),
        event_id=event_id,
        organization_id=str(org_id),
        award_requirement_id=str(requirement_id),
        awarded_grant_id=requirement.get("awarded_grant_id"),
        created_by_identity_id=accountable_identity(db, org_id),
        **declared_fields(body),
        **fixture_fields(),
    )
    refuse_if_blocked(result, wrote="proof_event")
    db.commit()
    return envelope(
        {
            "event_id": str(event_id),
            "award_requirement_id": str(requirement_id),
            "organization_id": str(org_id),
            "event_type": result.get("event_type"),
            "event_status": result.get("event_status"),
            "rows_written": int(result["rows_written"]),
        },
        immutable=True,
        document_storage_available=False,
    )


@router.get("/{org_id}/requirements/{requirement_id}/proof-events")
def list_proof_events(
    org_id: uuid.UUID,
    requirement_id: uuid.UUID,
    ctx: Annotated[OrgContext, Depends(require_demo_org_session)],
    db: Annotated[Session, Depends(get_db_session)],
    include_archived: bool = False,
) -> dict[str, Any]:
    same_org(org_id, ctx)
    result = repo.list_proof_events_for_requirement(
        connection=db.connection(),
        organization_id=str(org_id),
        award_requirement_id=str(requirement_id),
        include_archived=include_archived,
    )
    return envelope(
        {
            "organization_id": str(org_id),
            "award_requirement_id": str(requirement_id),
            "rows_read": int(result.get("rows_read") or 0),
            "events": list(result.get("events") or []),
            "live_count": int(result.get("live_count") or 0),
            "superseded_count": int(result.get("superseded_count") or 0),
        }
    )


@router.get("/{org_id}/proof-events/{event_id}")
def get_proof_event(
    org_id: uuid.UUID,
    event_id: uuid.UUID,
    ctx: Annotated[OrgContext, Depends(require_demo_org_session)],
    db: Annotated[Session, Depends(get_db_session)],
) -> dict[str, Any]:
    same_org(org_id, ctx)
    result = repo.get_proof_event(
        connection=db.connection(),
        organization_id=str(org_id),
        event_id=str(event_id),
    )
    refuse_if_absent(result, what="proof_event")
    return envelope(
        {
            "event_id": str(event_id),
            "organization_id": str(org_id),
            "event_type": result.get("event_type"),
            "event_status": result.get("event_status"),
            "superseded_at": result.get("superseded_at"),
            "archived_at": result.get("archived_at"),
            "rows_read": int(result["rows_read"]),
        },
        immutable=True,
    )


@router.post("/{org_id}/proof-events/{event_id}/supersede")
def supersede_proof_event(
    org_id: uuid.UUID,
    event_id: uuid.UUID,
    body: SupersedeBody,
    ctx: Annotated[OrgContext, Depends(require_demo_org_session)],
    db: Annotated[Session, Depends(get_db_session)],
) -> dict[str, Any]:
    """The only correction an immutable trail permits.

    A new event that names the one it replaces. The old row keeps every fact it
    recorded and gains a `superseded_at`; nothing it said is edited.
    """
    same_org(org_id, ctx)
    refuse_caller_supplied(body)
    refuse_body_storage(body)

    existing = repo.get_proof_event(
        connection=db.connection(),
        organization_id=str(org_id),
        event_id=str(event_id),
    )
    refuse_if_absent(existing, what="proof_event")

    replacement_id = uuid.uuid4()
    result = repo.supersede_proof_event(
        connection=db.connection(),
        organization_id=str(org_id),
        superseded_event_id=str(event_id),
        event_id=replacement_id,
        award_requirement_id=existing.get("award_requirement_id"),
        awarded_grant_id=existing.get("awarded_grant_id"),
        created_by_identity_id=accountable_identity(db, org_id),
        **declared_fields(body),
        **fixture_fields(),
    )
    refuse_if_blocked(result, wrote="proof_event_supersede")
    db.commit()
    return envelope(
        {
            "superseded_event_id": str(event_id),
            "event_id": str(replacement_id),
            "event_type": "proof_superseded",
            "organization_id": str(org_id),
            "rows_written": int(result["rows_written"]),
        },
        immutable=True,
        update_path_available=False,
        update_path_available_because=(
            "what was believed at the time is what the row says, forever; a "
            "correction is a new event that names the one it replaces"
        ),
    )


@router.post("/{org_id}/proof-events/{event_id}/archive")
def archive_proof_event(
    org_id: uuid.UUID,
    event_id: uuid.UUID,
    ctx: Annotated[OrgContext, Depends(require_demo_org_session)],
    db: Annotated[Session, Depends(get_db_session)],
) -> dict[str, Any]:
    same_org(org_id, ctx)
    result = repo.archive_proof_event(
        connection=db.connection(),
        organization_id=str(org_id),
        event_id=str(event_id),
    )
    refuse_if_blocked(result, wrote="proof_event_archive")
    db.commit()
    return envelope(
        {
            "event_id": str(event_id),
            "organization_id": str(org_id),
            "archived": True,
            "rows_written": int(result["rows_written"]),
        },
        immutable=True,
    )
