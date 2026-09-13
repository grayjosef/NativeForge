"""Gate 151E: persist a digest, read it back, list them, archive one.

```text
POST /v1/nf/demo/orgs/{org}/digest/persist          build and store
GET  /v1/nf/demo/orgs/{org}/digest/records          list
GET  /v1/nf/demo/orgs/{org}/digest/records/{id}     read one, hash checked
POST /v1/nf/demo/orgs/{org}/digest/records/{id}/archive
```

## What the POST does and does not do

It builds the digest the preview route would have shown and stores it. It sends
nothing, contacts no provider, calls no source, and touches no object store.

The labelling is forced: `is_demo` and `fact_status` come from the organization,
never from the body, and a body offering either gets a named refusal. Gate 137A
found a verified binding written onto the demo organization because the caller
said it was not one.

## What is stored

The normalized payload and a sha256 over it. No rendered body, no recipient, no
address — there are no columns for any of them in 0042, so a later mistake has
nowhere to put one.

## Archive is a state

An archived digest stays readable by id, because an audit of a missed deadline
needs the digest that was current at the time. It drops out of the default list
and comes back with `include_archived=true`.
"""

from __future__ import annotations

import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Body, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from nativeforge.api.customer_org_context_dependency import require_demo_org_session
from nativeforge.api.deps_db import get_db_session
from nativeforge.api.org_context import OrgContext
from nativeforge.api.post_award_common import envelope, same_org
from nativeforge.services.tenant_digest_persistence_service import (
    CONTROLLED_SCOPE,
    archive_digest,
    list_digests,
    persist_digest,
    persistence_invariant_failures,
    read_digest,
)

router = APIRouter(prefix="/v1/nf/demo/orgs", tags=["tenant-digest-persistence-demo"])

#: Body fields a caller may not set. The labelling is the organization's.
CALLER_MAY_NOT_SET: tuple[str, ...] = (
    "is_demo",
    "fact_status",
    "organization_id",
    "payload_sha256",
    "email_delivery_live",
    "source_monitoring_live",
)


def _build_digest(db: Session, org_id: uuid.UUID, cadence: str) -> dict[str, Any]:
    """The digest the preview route would have shown, shaped for storage.

    The preview assembler is the authority on what a digest says. This maps its
    field names onto the record's, and invents nothing: a persistence layer that
    recomputed a count would make the stored record disagree with the one the
    tenant saw.
    """
    from nativeforge.services.tenant_nofo_digest_builder_service import (
        build_digest_id,
    )
    from nativeforge.services.tenant_nofo_digest_service import (
        build_org_digest_preview,
    )

    preview = build_org_digest_preview(
        connection=db.connection(),
        organization_id=str(org_id),
        cadence=cadence,
    )
    if preview.get("blocked_reasons"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "error": "digest_not_produced",
                "blocked_reasons": preview["blocked_reasons"],
                "cadence": cadence,
            },
        )

    period_start = preview.get("period_start")
    period_end = preview.get("period_end")
    digest_id = preview.get("digest_id") or build_digest_id(
        tenant_id=str(org_id),
        cadence=preview.get("cadence") or cadence,
        period_start=period_start,
        period_end=period_end,
    )

    return {
        "digest_id": digest_id,
        "tenant_id": str(org_id),
        "cadence": preview.get("cadence") or cadence,
        "period_start": period_start,
        "period_end": period_end,
        "digest_period_key": f"{period_start}..{period_end}",
        "snapshot_ids": preview.get("snapshot_ids") or [],
        "items": preview.get("items") or [],
        "suppressed_items": preview.get("suppressed_items") or [],
        "items_total": int(preview.get("items_total") or 0),
        "items_visible": int(preview.get("items_visible") or 0),
        "items_suppressed": int(preview.get("items_suppressed") or 0),
        # The honesty counts, stored whether or not they are zero.
        "items_human_review": int(
            preview.get("items_with_unresolved_eligibility") or 0
        ),
        "items_with_unverified_deadlines": int(
            preview.get("items_with_unverified_deadlines") or 0
        ),
        "items_with_unknown_reporting_burden": int(
            preview.get("items_with_unknown_reporting_burden") or 0
        ),
        "caveats": preview.get("caveats") or [],
        "blocked_reasons": preview.get("blocked_reasons") or [],
        "delivery_status": preview.get("delivery_status") or "preview_only",
    }


@router.post("/{org_id}/digest/persist", status_code=status.HTTP_201_CREATED)
def persist_current_digest(
    org_id: uuid.UUID,
    ctx: Annotated[OrgContext, Depends(require_demo_org_session)],
    db: Annotated[Session, Depends(get_db_session)],
    body: Annotated[dict[str, Any] | None, Body()] = None,
) -> dict[str, Any]:
    """Build the current digest and store it. Sends nothing."""
    same_org(org_id, ctx)
    supplied = body or {}

    offered = sorted(key for key in supplied if key in CALLER_MAY_NOT_SET)
    if offered:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "error": "caller_may_not_set_these_fields",
                "fields": offered,
                "scope": CONTROLLED_SCOPE,
            },
        )

    cadence = str(supplied.get("cadence") or "weekly").strip().lower()
    digest = _build_digest(db, org_id, cadence)

    result = persist_digest(
        connection=db.connection(),
        organization_id=str(org_id),
        digest=digest,
        org_is_demo=True,
        scope=CONTROLLED_SCOPE,
    )
    failures = persistence_invariant_failures(result)
    if failures:
        raise HTTPException(status_code=500, detail="digest_persistence_refused")

    if not result["persisted"]:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "error": "digest_was_not_persisted",
                "blocked_reasons": result["blocked_reasons"],
                "scope": CONTROLLED_SCOPE,
            },
        )

    return envelope(
        {
            "digest_id": result["digest_id"],
            "payload_sha256": result["payload_sha256"],
            "persisted": True,
            "rendered_body_stored": False,
            "recipient_stored": False,
            "email_sent": False,
            "live_source_called": False,
            "object_store_contacted": False,
        }
    )


@router.get("/{org_id}/digest/records")
def list_digest_records_route(
    org_id: uuid.UUID,
    ctx: Annotated[OrgContext, Depends(require_demo_org_session)],
    db: Annotated[Session, Depends(get_db_session)],
    include_archived: Annotated[bool, Query()] = False,
) -> dict[str, Any]:
    """Every persisted digest for this organization."""
    same_org(org_id, ctx)
    result = list_digests(
        connection=db.connection(),
        organization_id=str(org_id),
        include_archived=include_archived,
    )
    return envelope(
        {
            "count": result["count"],
            "include_archived": include_archived,
            "records": [
                {
                    key: value
                    for key, value in record.items()
                    # The payload is available by id; a list of them would make
                    # a listing route the largest response in the API.
                    if key != "digest_payload_json"
                }
                for record in result["records"]
            ],
        }
    )


@router.get("/{org_id}/digest/records/{digest_id}")
def get_digest_record_route(
    org_id: uuid.UUID,
    digest_id: str,
    ctx: Annotated[OrgContext, Depends(require_demo_org_session)],
    db: Annotated[Session, Depends(get_db_session)],
) -> dict[str, Any]:
    """One persisted digest, with its hash checked against the stored payload."""
    same_org(org_id, ctx)
    result = read_digest(
        connection=db.connection(),
        organization_id=str(org_id),
        digest_id=digest_id,
    )
    if not result["found"]:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "digest_record_not_found"},
        )

    return envelope(
        {
            "record": result["record"],
            "payload_hash_verified": result["payload_hash_verified"],
        }
    )


@router.post("/{org_id}/digest/records/{digest_id}/archive")
def archive_digest_record_route(
    org_id: uuid.UUID,
    digest_id: str,
    ctx: Annotated[OrgContext, Depends(require_demo_org_session)],
    db: Annotated[Session, Depends(get_db_session)],
) -> dict[str, Any]:
    """Archive one digest. It stays readable by id."""
    same_org(org_id, ctx)
    result = archive_digest(
        connection=db.connection(),
        organization_id=str(org_id),
        digest_id=digest_id,
    )
    if not result["archived"]:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "error": "digest_record_was_not_archived",
                "blocked_reasons": result["blocked_reasons"],
            },
        )

    return envelope(
        {
            "digest_id": result["digest_id"],
            "archived": True,
            "still_readable_by_id": True,
        }
    )
