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
    object_store_configured,
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
        object_store_configured=object_store_configured(),
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
        object_store_configured=object_store_configured(),
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
        object_store_configured=object_store_configured(),
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


# ---------------------------------------------------------------------------
# Gate 141D: the body, which this deployment cannot store
# ---------------------------------------------------------------------------
#
# An EXPLICIT refusal, not a silent absence. Gate 139 left no route at all for
# a document's bytes, which meant a caller asking for one got a 404 that reads
# as "wrong URL" rather than "this deployment has nowhere to put a file". A
# refusal that names itself is the difference between a missing feature and a
# feature that was decided against.
#
# The permitted branch is REACHABLE, through `get_document_body_adapter`. In
# runtime that dependency yields nothing and every upload is refused; a test
# overrides it with the in-memory fake and proves the storing path works. An
# unreachable permitted branch makes every refusal above it unfalsifiable -
# Gate 134F removed exactly that from the customer-auth chain.
#
# Runtime cannot reach the storing branch by any configuration of its own:
# nothing constructs an adapter for this dependency, and there is no SDK in
# this project to construct an external one from.


def get_document_body_adapter() -> Any:
    """The adapter this deployment stores document bytes through.

    ``None`` — and that is the answer, not a placeholder. Overridden in a test
    with `InMemoryObjectStorageAdapter` so the storing branch is reachable and
    provable without a bucket, a credential or a network.
    """
    return None


class DocumentBodyRequest(BaseModel):
    """What a caller may say when asking to store a document's bytes.

    No field carries content. `content_length` and `sha256_digest` describe
    bytes the caller has; they are not the bytes, and the route refuses before
    anything could be read from them anyway.
    """

    content_type: str | None = Field(default=None, max_length=128)
    content_length: int | None = Field(default=None, ge=0)
    sha256_digest: str | None = Field(default=None, max_length=64)

    model_config = {"extra": "allow"}


@router.get("/{org_id}/documents/{document_id}/body-storage")
def get_document_body_storage_readiness(
    org_id: uuid.UUID,
    document_id: uuid.UUID,
    ctx: Annotated[OrgContext, Depends(require_demo_org_session)],
    adapter: Annotated[Any, Depends(get_document_body_adapter)],
) -> dict[str, Any]:
    """Can this document's bytes be stored, and if not, what is missing?

    Answered without touching the document row: whether an object store exists
    is a property of the deployment, not of one document, and reading the row
    first would make an unconfigured store look like a missing document.
    """
    same_org(org_id, ctx)

    from nativeforge.services.object_storage_configuration_preflight_service import (
        build_object_storage_preflight,
    )

    preflight = build_object_storage_preflight()
    available = adapter is not None and bool(preflight["object_store_configured"])

    return envelope(
        {
            "document_id": str(document_id),
            "organization_id": str(org_id),
            "body_storage_available": available,
            "adapter_available": adapter is not None,
            "adapter_kind": getattr(adapter, "adapter_kind", None),
            "object_store_configured": preflight["object_store_configured"],
            "preflight_state": preflight["state"],
            # Key NAMES, never values. A reader needs to know what to fill in.
            "missing_configuration": preflight["absent_key_names"],
            "unavailable_reason": None if available else BODY_STORAGE_UNAVAILABLE,
        },
        metadata_only=True,
        production_storage=False,
    )


@router.post(
    "/{org_id}/documents/{document_id}/body",
    status_code=status.HTTP_201_CREATED,
)
def store_document_body(
    org_id: uuid.UUID,
    document_id: uuid.UUID,
    body: DocumentBodyRequest,
    ctx: Annotated[OrgContext, Depends(require_demo_org_session)],
    db: Annotated[Session, Depends(get_db_session)],
    adapter: Annotated[Any, Depends(get_document_body_adapter)],
) -> dict[str, Any]:
    """Store a document's bytes. Refused, with the reason, unless an adapter exists.

    No request body carries content and none is read. The route exists to give
    the refusal a name and to keep the storing branch reachable for a test; it
    is not a stub that pretends a file was saved.
    """
    same_org(org_id, ctx)
    refuse_caller_supplied(body)

    from nativeforge.services.object_storage_adapter_service import (
        MAX_BODY_BYTES,
        body_digest,
    )
    from nativeforge.services.object_storage_configuration_preflight_service import (
        build_object_storage_preflight,
    )

    # A caller may not name the location. Refused before anything else, because
    # a caller-chosen key is how one tenant writes into another's prefix.
    offered = getattr(body, "model_extra", None) or {}
    if "object_key" in offered or "object_bucket" in offered:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "error": "caller_supplied_object_keys_are_not_accepted",
                "because": (
                    "an object key is derived from the organization and "
                    "document ids; accepting one lets a caller choose which "
                    "tenant's prefix their bytes land in"
                ),
            },
        )

    preflight = build_object_storage_preflight()
    if adapter is None or not preflight["object_store_configured"]:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "error": BODY_STORAGE_UNAVAILABLE,
                "object_store_configured": preflight["object_store_configured"],
                "adapter_available": adapter is not None,
                "preflight_state": preflight["state"],
                "missing_configuration": preflight["absent_key_names"],
                "because": (
                    "this deployment has no object store; a document row is a "
                    "reference and its bytes live nowhere"
                ),
            },
        )

    found = repo.get_award_document(
        connection=db.connection(),
        organization_id=str(org_id),
        document_id=str(document_id),
    )
    refuse_if_absent(found, what="award_document")

    # Synthetic, and only reachable when a test injected an adapter. Runtime
    # never gets here: no real customer file is read, opened or hashed.
    payload = f"gate141 body placeholder for {document_id}".encode()
    stored = adapter.put(
        organization_id=str(org_id),
        document_id=str(document_id),
        body=payload,
        content_type=body.content_type,
        declared_digest=body_digest(payload),
    )
    if not stored.get("stored"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "error": "document_body_was_not_stored",
                # The adapter's own reasons, unchanged. Paraphrasing them into
                # an HTTP message would be a second, worse contract.
                "blocked_reasons": sorted(stored.get("blocked_reasons") or []),
                "max_body_bytes": MAX_BODY_BYTES,
            },
        )

    return envelope(
        {
            "document_id": str(document_id),
            "organization_id": str(org_id),
            # The key, the length and the digest. Never the bytes.
            "object_key": stored["object_key"],
            "content_length": stored["content_length"],
            "sha256_digest": stored["sha256_digest"],
            "max_body_bytes": MAX_BODY_BYTES,
            "adapter_kind": stored["adapter_kind"],
            "storage_scope": (
                "production" if getattr(adapter, "external", False) else "hermetic_fake"
            ),
        },
        metadata_only=False,
        document_body_written=True,
        object_store_contacted=bool(stored["external_object_store_contacted"]),
        object_store_configured=preflight["object_store_configured"],
        production_storage=False,
        body_bytes_returned=False,
    )
