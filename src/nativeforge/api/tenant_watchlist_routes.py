"""Gate 140E: the source watchlist, behind an authenticated organization context.

```text
GET    /v1/nf/demo/orgs/{org}/source-watchlist                   list
POST   /v1/nf/demo/orgs/{org}/source-watchlist                   add
GET    /v1/nf/demo/orgs/{org}/source-watchlist/{entry_id}        read one
POST   /v1/nf/demo/orgs/{org}/source-watchlist/{entry_id}/archive  stop watching
```

Demo organizations only, for the reason Gate 139 recorded: a real-organization
router would create a route to `aaaaaaaa-…` that nobody has authorized.

## Watching is not monitoring

Every response carries `source_monitoring_live: false` and every entry carries
it too, so a reader of one line does not have to find the header to learn it.
Nothing here calls a source, activates a collector, or opens a socket — a
watchlist entry is a statement of interest, and this gate is careful not to let
it read as a statement of coverage.

## A registry claim is checked

`watchlist_source: registry_entry` is verified against the 177 source ids in
the seed catalogue this repository ships. An id that is not there is refused by
name rather than accepted on the caller's word, and a `controlled_fixture` id
must carry the fixture prefix so nothing later mistakes it for a registry
entry.

`tenant_requested` is allowed and is stored with `human_review_required: true`.
A source nobody has vetted is exactly the thing a human has to look at, and
refusing it outright would push tenants into mislabelling.
"""

from __future__ import annotations

import uuid
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
    refuse_caller_supplied,
    refuse_if_absent,
    refuse_if_blocked,
    same_org,
)
from nativeforge.services import tenant_source_watchlist_service as repo

router = APIRouter(prefix="/v1/nf/demo/orgs", tags=["tenant-source-watchlist-demo"])


class WatchlistEntryBody(BaseModel):
    """What a caller may say about a source they want to watch.

    Vocabularies are the repository's, unvalidated here: restating
    `WATCHLIST_SOURCES` in a pydantic Enum would be a second copy that could
    drift from the CHECK constraint. The repository refuses an unrecognised
    value by name and that reason reaches the caller unchanged.
    """

    source_id: str = Field(min_length=1, max_length=512)
    watchlist_source: str = Field(min_length=1, max_length=32)
    watchlist_state: str = Field(default="watching", max_length=32)
    source_name: str | None = Field(default=None, max_length=512)
    jurisdiction: str | None = Field(default=None, max_length=64)
    program_area: str | None = Field(default=None, max_length=128)

    # `extra="allow"` so `refuse_caller_supplied` can SEE a field a caller
    # should not set. Pydantic drops an unknown field silently, which is how
    # Gate 139 found `is_demo: false` being ignored rather than refused.
    model_config = {"extra": "allow"}


@router.post("/{org_id}/source-watchlist", status_code=status.HTTP_201_CREATED)
def add_watchlist_entry(
    org_id: uuid.UUID,
    body: WatchlistEntryBody,
    ctx: Annotated[OrgContext, Depends(require_demo_org_session)],
    db: Annotated[Session, Depends(get_db_session)],
) -> dict[str, Any]:
    same_org(org_id, ctx)
    refuse_caller_supplied(body)

    entry_id = uuid.uuid4()
    result = repo.add_watchlist_entry(
        connection=db.connection(),
        entry_id=entry_id,
        organization_id=str(org_id),
        created_by_identity_id=accountable_identity(db, org_id),
        fact_status="demo_fixture",
        is_demo=True,
        **declared_fields(body),
    )
    refuse_if_blocked(result, wrote="watchlist_entry")
    db.commit()
    return envelope(
        {
            "entry_id": str(entry_id),
            "organization_id": str(org_id),
            "source_id": result.get("source_id"),
            "watchlist_state": result.get("watchlist_state"),
            "watchlist_source": result.get("watchlist_source"),
            "human_review_required": bool(result.get("human_review_required")),
            "registry_source_count": int(result.get("registry_source_count") or 0),
            "rows_written": int(result["rows_written"]),
        },
        source_monitoring_live=False,
        live_source_called=False,
    )


@router.get("/{org_id}/source-watchlist")
def list_watchlist(
    org_id: uuid.UUID,
    ctx: Annotated[OrgContext, Depends(require_demo_org_session)],
    db: Annotated[Session, Depends(get_db_session)],
    include_archived: bool = False,
    jurisdiction: str | None = None,
) -> dict[str, Any]:
    same_org(org_id, ctx)
    result = repo.list_watchlist(
        connection=db.connection(),
        organization_id=str(org_id),
        include_archived=include_archived,
        jurisdiction=jurisdiction,
    )
    return envelope(
        {
            "organization_id": str(org_id),
            "rows_read": int(result.get("rows_read") or 0),
            "entries": list(result.get("entries") or []),
            "active_count": int(result.get("active_count") or 0),
            "human_review_count": int(result.get("human_review_count") or 0),
        },
        source_monitoring_live=False,
        live_source_called=False,
    )


@router.get("/{org_id}/source-watchlist/{entry_id}")
def get_watchlist_entry(
    org_id: uuid.UUID,
    entry_id: uuid.UUID,
    ctx: Annotated[OrgContext, Depends(require_demo_org_session)],
    db: Annotated[Session, Depends(get_db_session)],
) -> dict[str, Any]:
    same_org(org_id, ctx)
    result = repo.get_watchlist_entry(
        connection=db.connection(),
        organization_id=str(org_id),
        entry_id=str(entry_id),
    )
    refuse_if_absent(result, what="watchlist_entry")
    return envelope(
        {
            "entry_id": str(entry_id),
            "organization_id": str(org_id),
            "source_id": result.get("source_id"),
            "watchlist_state": result.get("watchlist_state"),
            "watchlist_source": result.get("watchlist_source"),
            "human_review_required": bool(result.get("human_review_required")),
            "rows_read": int(result["rows_read"]),
        },
        source_monitoring_live=False,
        last_checked_at=None,
    )


@router.post("/{org_id}/source-watchlist/{entry_id}/archive")
def archive_watchlist_entry(
    org_id: uuid.UUID,
    entry_id: uuid.UUID,
    ctx: Annotated[OrgContext, Depends(require_demo_org_session)],
    db: Annotated[Session, Depends(get_db_session)],
) -> dict[str, Any]:
    """Stop watching. The row stays, so the history stays."""
    same_org(org_id, ctx)
    result = repo.archive_watchlist_entry(
        connection=db.connection(),
        organization_id=str(org_id),
        entry_id=str(entry_id),
    )
    refuse_if_blocked(result, wrote="watchlist_entry_archive")
    db.commit()
    return envelope(
        {
            "entry_id": str(entry_id),
            "organization_id": str(org_id),
            "archived": True,
            "rows_written": int(result["rows_written"]),
            "rows_deleted": 0,
        },
        history_preserved=True,
    )
