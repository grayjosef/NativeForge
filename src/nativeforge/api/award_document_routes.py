"""Gate 139E: document metadata. A reference, never a body.

## No bytes, and the database agrees

```sql
-- nf_award_documents
object_key IS NULL OR object_store_configured
```

`object_store_configured` is bridged from Gate 96's `detect_body_store_mode()`,
never accepted from a caller, and reports `unconfigured` today. So the schema
itself refuses an `object_key`, and metadata-only is not a convention this gate
chose — it is what the table permits.

A caller offering `object_key`, `content`, `body`, `bytes`, `sha256_digest` or
`content_length` gets **422 with a named reason**, not a 500 and not a silent
drop:

```text
document_body_storage_is_not_configured
```

Refusing by name rather than ignoring is the rule Gates 110-113 settled for
labels: a caller that offered something should learn it was not honoured.

## Attached to something

```text
awarded_grant_id      nullable
award_requirement_id  nullable
proof_event_id        nullable
```

All three optional, at least one required — *"a document attached to nothing is
a file in a drawer"*. All three are in `FORBIDDEN_ANCHOR_NAMES`: reaching the
organization through whichever join happened to be populated would make this
table's policy depend on three other tables' policies.

## Legal hold refuses archive

`archive_award_document` returns `legal_hold_refuses_archive` rather than
archiving, and the database refuses it too. That reason reaches the caller
unchanged.
"""

from __future__ import annotations

import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from nativeforge.api.customer_org_context_dependency import require_demo_org_session
from nativeforge.api.deps_db import get_db_session
from nativeforge.api.org_context import OrgContext
from nativeforge.api.post_award_common import (
    BODY_STORAGE_UNAVAILABLE,
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
from nativeforge.services import award_document_store_repository_service as repo
from nativeforge.services import awarded_grants_repository_service as award_repo

router = APIRouter(prefix="/v1/nf/demo/orgs", tags=["award-documents-demo"])


class DocumentBody(BaseModel):
    """A reference. Every body-bearing field is absent by design.

    `refuse_body_storage` rejects them if a caller sends one anyway - pydantic
    would otherwise drop an unknown field silently, and a silent drop is how a
    caller comes to believe a file was stored.
    """

    document_kind: str = Field(min_length=1, max_length=64)
    document_status: str = Field(min_length=1, max_length=64)
    document_title: str = Field(min_length=1, max_length=1024)
    document_description: str | None = Field(default=None, max_length=8192)
    document_source: str = Field(min_length=1, max_length=64)
    document_source_ref: str | None = Field(default=None, max_length=512)
    retention_class: str = Field(min_length=1, max_length=64)
    award_requirement_id: uuid.UUID | None = None
    proof_event_id: uuid.UUID | None = None
    customer_visible: bool = False
    legal_hold: bool = False

    model_config = {"extra": "allow"}


@router.post(
    "/{org_id}/awarded-grants/{award_id}/documents",
    status_code=status.HTTP_201_CREATED,
)
def create_document_reference(
    org_id: uuid.UUID,
    award_id: uuid.UUID,
    body: DocumentBody,
    ctx: Annotated[OrgContext, Depends(require_demo_org_session)],
    db: Annotated[Session, Depends(get_db_session)],
) -> dict[str, Any]:
    same_org(org_id, ctx)
    refuse_caller_supplied(body)
    # Before anything else: a caller trying to store a file learns it cannot.
    refuse_body_storage(body)

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

    document_id = uuid.uuid4()
    fields = declared_fields(body)
    for relationship in ("award_requirement_id", "proof_event_id"):
        if fields.get(relationship) is not None:
            fields[relationship] = str(fields[relationship])

    result = repo.create_award_document(
        connection=db.connection(),
        document_id=document_id,
        organization_id=str(org_id),
        awarded_grant_id=str(award_id),
        created_by_identity_id=accountable_identity(db, org_id),
        **fields,
        **fixture_fields(),
    )
    refuse_if_blocked(result, wrote="award_document")
    db.commit()
    return envelope(
        {
            "document_id": str(document_id),
            "awarded_grant_id": str(award_id),
            "organization_id": str(org_id),
            "document_status": result.get("document_status"),
            "rows_written": int(result["rows_written"]),
        },
        metadata_only=True,
        object_store_configured=False,
        body_storage_unavailable_reason=BODY_STORAGE_UNAVAILABLE,
    )


@router.get("/{org_id}/awarded-grants/{award_id}/documents")
def list_documents(
    org_id: uuid.UUID,
    award_id: uuid.UUID,
    ctx: Annotated[OrgContext, Depends(require_demo_org_session)],
    db: Annotated[Session, Depends(get_db_session)],
    include_archived: bool = False,
) -> dict[str, Any]:
    same_org(org_id, ctx)
    result = repo.list_documents_for_award(
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
            "documents": list(result.get("documents") or []),
        },
        metadata_only=True,
        object_store_configured=False,
    )


@router.get("/{org_id}/documents/{document_id}")
def get_document(
    org_id: uuid.UUID,
    document_id: uuid.UUID,
    ctx: Annotated[OrgContext, Depends(require_demo_org_session)],
    db: Annotated[Session, Depends(get_db_session)],
) -> dict[str, Any]:
    same_org(org_id, ctx)
    result = repo.get_award_document(
        connection=db.connection(),
        organization_id=str(org_id),
        document_id=str(document_id),
    )
    refuse_if_absent(result, what="award_document")
    return envelope(
        {
            "document_id": str(document_id),
            "organization_id": str(org_id),
            "document_status": result.get("document_status"),
            "document_kind": result.get("document_kind"),
            "legal_hold": bool(result.get("legal_hold")),
            "archived_at": result.get("archived_at"),
            "rows_read": int(result["rows_read"]),
        },
        metadata_only=True,
        object_store_configured=False,
        # There is no download. The row describes a document; it does not
        # contain one, and no route here will pretend otherwise.
        body_available=False,
    )


@router.post("/{org_id}/documents/{document_id}/archive")
def archive_document(
    org_id: uuid.UUID,
    document_id: uuid.UUID,
    ctx: Annotated[OrgContext, Depends(require_demo_org_session)],
    db: Annotated[Session, Depends(get_db_session)],
) -> dict[str, Any]:
    """Archive, unless a lawyer said not to.

    `legal_hold_refuses_archive` reaches the caller unchanged: a document under
    legal hold is one somebody has said must not move, and archiving is the
    only lifecycle operation this table has.
    """
    same_org(org_id, ctx)
    result = repo.archive_award_document(
        connection=db.connection(),
        organization_id=str(org_id),
        document_id=str(document_id),
    )
    refuse_if_blocked(result, wrote="award_document_archive")
    db.commit()
    return envelope(
        {
            "document_id": str(document_id),
            "organization_id": str(org_id),
            "archived": True,
            "rows_written": int(result["rows_written"]),
        },
        metadata_only=True,
    )
