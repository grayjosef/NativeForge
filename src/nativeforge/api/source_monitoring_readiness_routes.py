"""Gate 143G: source monitoring readiness, behind an authenticated org context.

```text
GET  /v1/nf/demo/orgs/{org}/source-monitoring/readiness   what is and is not ready
GET  /v1/nf/demo/orgs/{org}/source-monitoring/blockers     why each class is blocked
POST /v1/nf/demo/orgs/{org}/source-monitoring/evaluate     one watchlist source
```

## Nothing here fetches

No URL is opened, no robots.txt is read, no DNS is resolved, and no collector is
started. Every response carries `fetch_performed: false`,
`collector_activated: false` and `source_monitoring_live: false`.

A source's `source_url` is returned as **text** — it is what the registry says,
and a reader needs it to go and look at the terms themselves. Returning it is
not fetching it.

## No API key value, ever

The evaluation reports that a credential is *required* and whether one is
*present*. Neither route returns a key, a prefix of one, or its length.

## Evaluate takes a source a tenant is already watching

Gate 140 made the watchlist real and documented the distinction this route has
to hold: **watching is not monitoring**. So `evaluate` answers "what would block
monitoring this source", for a source the organization has actually put on its
watchlist — and refuses one it has not.
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
from nativeforge.api.post_award_common import envelope, refuse_caller_supplied, same_org
from nativeforge.services import tenant_source_watchlist_service as watchlist
from nativeforge.services.source_collector_configuration_preflight_service import (
    build_collector_preflight,
)
from nativeforge.services.source_monitoring_approved_source_service import (
    evaluate_registry,
    evaluate_source,
)
from nativeforge.services.source_monitoring_readiness_service import (
    build_source_monitoring_readiness,
)

router = APIRouter(prefix="/v1/nf/demo/orgs", tags=["source-monitoring-demo"])

#: A dry-run collector, fully declared. Used to prove the preflight runs; it
#: requests no live fetch and could not perform one if it did.
DRY_RUN_COLLECTOR: dict[str, Any] = {
    "fetch_mode": "dry_run",
    "rate_limit_policy": "polite_default",
    "attribution_requirement": "not_required",
    "user_agent_policy": "nativeforge_canonical",
    "raw_payload_storage_policy": "local_dev_ignored",
    "activation_approval": False,
}


class EvaluateBody(BaseModel):
    """Which watched source to evaluate. No terms status, no approval.

    A caller cannot supply either: a terms review is something a human records
    and an activation approval is a decision, and accepting them here would let
    a request talk itself past both.
    """

    source_id: str = Field(min_length=1, max_length=512)

    model_config = {"extra": "allow"}


def _readiness(db: Session, org_id: uuid.UUID) -> dict[str, Any]:
    entries = watchlist.list_watchlist(
        connection=db.connection(), organization_id=str(org_id)
    )
    known = watchlist.known_registry_source_ids()
    watched = [
        entry.get("source_id")
        for entry in (entries.get("entries") or [])
        if entry.get("source_id")
    ]
    return build_source_monitoring_readiness(
        collector_preflight=build_collector_preflight(
            config={**DRY_RUN_COLLECTOR, "source_id": watched[0] if watched else ""},
        ),
        watchlist_can_name_sources=bool(known),
        tenant_digest_operational=True,
    )


@router.get("/{org_id}/source-monitoring/readiness")
def get_source_monitoring_readiness(
    org_id: uuid.UUID,
    ctx: Annotated[OrgContext, Depends(require_demo_org_session)],
    db: Annotated[Session, Depends(get_db_session)],
) -> dict[str, Any]:
    """What is ready to evaluate, and what activation would still need."""
    same_org(org_id, ctx)
    readiness = _readiness(db, org_id)

    return envelope(
        {
            "organization_id": str(org_id),
            "source_monitoring_preflight_ready": readiness[
                "source_monitoring_preflight_ready"
            ],
            "source_monitoring_live": readiness["source_monitoring_live"],
            "scope": readiness["scope"],
            "registry_row_count": readiness["registry_row_count"],
            "by_state": readiness["by_state"],
            "monitorable_count": readiness["monitorable_count"],
            "chokepoint_clean": readiness["chokepoint_clean"],
            "chokepoint_files_scanned": readiness["chokepoint_files_scanned"],
            "scheduler_runtime_mode": readiness["scheduler_runtime_mode"],
            "scheduler_components_missing": readiness["scheduler_components_missing"],
            "monitorable_source_required_for_readiness": readiness[
                "monitorable_source_required_for_readiness"
            ],
            "blocked_reasons": readiness["blocked_reasons"],
        },
        fetch_performed=False,
        collector_activated=False,
        source_monitoring_live=False,
        live_source_coverage=False,
        production_source_monitoring=False,
        api_key_values_reported=False,
    )


@router.get("/{org_id}/source-monitoring/blockers")
def get_source_monitoring_blockers(
    org_id: uuid.UUID,
    ctx: Annotated[OrgContext, Depends(require_demo_org_session)],
    db: Annotated[Session, Depends(get_db_session)],
) -> dict[str, Any]:
    """Why each class of source is blocked, named with its owner."""
    same_org(org_id, ctx)
    readiness = _readiness(db, org_id)
    evaluation = evaluate_registry()

    return envelope(
        {
            "organization_id": str(org_id),
            "activation_blockers": readiness["activation_blockers"],
            "by_state": evaluation["by_state"],
            "terms_blocked_count": evaluation["terms_blocked_count"],
            "human_review_blocked_count": evaluation["human_review_blocked_count"],
            "api_key_missing_count": evaluation["api_key_missing_count"],
            "activation_approved_count": evaluation["activation_approved_count"],
            "monitorable_source_ids": evaluation["monitorable_source_ids"],
        },
        fetch_performed=False,
        collector_activated=False,
        source_monitoring_live=False,
        api_key_values_reported=False,
    )


@router.post("/{org_id}/source-monitoring/evaluate")
def evaluate_watched_source(
    org_id: uuid.UUID,
    body: EvaluateBody,
    ctx: Annotated[OrgContext, Depends(require_demo_org_session)],
    db: Annotated[Session, Depends(get_db_session)],
) -> dict[str, Any]:
    """What would block monitoring one source this organization watches.

    Refuses a source the organization has not put on its watchlist: answering
    for an arbitrary id would make this a registry lookup with a session
    attached, rather than something about this tenant.
    """
    same_org(org_id, ctx)
    refuse_caller_supplied(body)

    entries = watchlist.list_watchlist(
        connection=db.connection(), organization_id=str(org_id)
    )
    watched = {
        entry.get("source_id")
        for entry in (entries.get("entries") or [])
        if entry.get("source_id")
    }
    if body.source_id not in watched:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": "this_organization_does_not_watch_this_source",
                "source_id": body.source_id,
                "watched_count": len(watched),
            },
        )

    # Runtime supplies no recorded terms review and no activation approval,
    # so this evaluates to whatever the registry alone can support.
    evaluation = evaluate_source(source_id=body.source_id)

    return envelope(
        {
            "organization_id": str(org_id),
            "source_id": evaluation["source_id"],
            "state": evaluation["state"],
            "monitorable": evaluation["monitorable"],
            "registry_known": evaluation["registry_known"],
            "terms_status": evaluation["terms_status"],
            "human_review_required": evaluation["human_review_required"],
            "credential_required": evaluation["credential_required"],
            "access_posture": evaluation["access_posture"],
            "resolver_url_status": evaluation["resolver_url_status"],
            "source_health_status": evaluation["source_health_status"],
            # The registry's own url, as text. A reader needs it to go and read
            # the terms; returning it is not fetching it.
            "source_url": evaluation["source_url"],
            "activation_approved": evaluation["activation_approved"],
            "blocked_reasons": evaluation["blocked_reasons"],
        },
        fetch_performed=False,
        robots_fetched=False,
        dns_resolved=False,
        collector_activated=False,
        source_monitoring_live=False,
        api_key_values_reported=False,
    )
