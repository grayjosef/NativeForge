"""Gate 140E: the digest preview and pursuit suppression, org-scoped.

```text
GET    /v1/nf/demo/orgs/{org}/digest                     weekly by default
GET    /v1/nf/demo/orgs/{org}/digest?cadence=daily       if the profile enables it
GET    /v1/nf/demo/orgs/{org}/digest/readiness           what is and is not ready
POST   /v1/nf/demo/orgs/{org}/digest/cadence             enable or disable daily
POST   /v1/nf/demo/orgs/{org}/digest/suppress            start a pursuit, hide it
POST   /v1/nf/demo/orgs/{org}/digest/lift                stop hiding it
```

## The digest sends nothing and fetches nothing

Every response carries `delivery_status: preview_only`,
`email_delivery_live: false`, `source_monitoring_live: false`,
`live_source_coverage: false` and `candidate_provenance:
labelled_fixture_snapshots`. An invariant fails if any of the first four is
ever true.

## Suppression needs audit evidence, and the route supplies it

`tenant_pursuit_suppression_service` refuses a suppression without an
`audit_event_id`:

```text
contract:no_audit_event_recorded
```

That refusal is right — suppressing an opportunity is an act somebody took, and
a suppression nobody can trace is a way for things to quietly stop appearing.
So this route **appends a real `nf_audit_events` row first** and passes its id.
It does not mint an id and hope: if the audit append fails, no suppression is
written.

## Suppression hides a view; it deletes nothing

The row keeps `source_history_preserved` and `provenance_preserved`, both
required true by a CHECK. The suppressed item stays in the digest's
`items_suppressed` count and in `suppressed_items`, so a tenant can always see
that something was withheld and go look at it.
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
    accountable_identity,
    envelope,
    refuse_caller_supplied,
    refuse_if_blocked,
    same_org,
)
from nativeforge.domain.enums import AuditAction
from nativeforge.repositories.audit_events import append_org_audit_event
from nativeforge.services import tenant_pursuit_suppression_repository_service as supp
from nativeforge.services.tenant_nofo_digest_service import (
    build_org_digest_preview,
    digest_preview_invariant_failures,
)

router = APIRouter(prefix="/v1/nf/demo/orgs", tags=["tenant-digest-demo"])

#: The cadences a caller may ask for. `weekly` is the default and needs no
#: setting; `daily` needs the profile to have enabled it.
CADENCES = frozenset({"weekly", "daily"})


class CadenceBody(BaseModel):
    """Enable or disable the daily alert.

    The setting lives in `nf_tenant_beta_profiles.digest_frequency`, which is a
    stored column - so this is a profile write, not a flag the digest service
    keeps. `none` is the vocabulary's way of saying no digest at all.
    """

    digest_frequency: str = Field(min_length=1, max_length=16)

    model_config = {"extra": "allow"}


class SuppressBody(BaseModel):
    opportunity_id: str = Field(min_length=1, max_length=512)
    suppression_reason: str = Field(min_length=1, max_length=48)
    pursuit_record_id: str | None = Field(default=None, max_length=512)

    model_config = {"extra": "allow"}


class LiftBody(BaseModel):
    opportunity_id: str = Field(min_length=1, max_length=512)

    model_config = {"extra": "allow"}


def _refuse_unknown_cadence(cadence: str) -> None:
    if cadence not in CADENCES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "error": "cadence_not_recognised",
                "cadence": cadence,
                "recognised": sorted(CADENCES),
            },
        )


@router.get("/{org_id}/digest")
def get_digest_preview(
    org_id: uuid.UUID,
    ctx: Annotated[OrgContext, Depends(require_demo_org_session)],
    db: Annotated[Session, Depends(get_db_session)],
    cadence: str = "weekly",
) -> dict[str, Any]:
    """The preview. Weekly unless the caller asks for daily and may have it."""
    same_org(org_id, ctx)
    _refuse_unknown_cadence(cadence)

    preview = build_org_digest_preview(
        connection=db.connection(),
        organization_id=str(org_id),
        cadence=cadence,
    )
    fails = digest_preview_invariant_failures(preview)
    if fails:
        # An invariant failure here is a bug in the assembler, not a caller
        # error. 500 rather than 422: nothing the caller sent caused it.
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "digest_invariant_failed", "failures": fails},
        )
    if preview["blocked_reasons"]:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "error": "digest_not_produced",
                "blocked_reasons": preview["blocked_reasons"],
                "cadence": cadence,
                "daily_alerts_enabled": preview["daily_alerts_enabled"],
            },
        )

    return envelope(
        {
            "organization_id": str(org_id),
            "cadence": preview["cadence"],
            "default_cadence": preview["default_cadence"],
            "daily_alerts_enabled": preview["daily_alerts_enabled"],
            "watchlist_entry_count": preview["watchlist_entry_count"],
            "items": preview["items"],
            "items_visible": preview["items_visible"],
            "items_suppressed": preview["items_suppressed"],
            "items_total": preview["items_total"],
            "suppressed_items": preview["suppressed_items"],
            "items_with_unresolved_eligibility": preview[
                "items_with_unresolved_eligibility"
            ],
            "items_with_unverified_deadlines": preview[
                "items_with_unverified_deadlines"
            ],
            "caveats": preview["caveats"],
            "delivery_status": preview["delivery_status"],
            "candidate_provenance": preview["candidate_provenance"],
        },
        source_monitoring_live=False,
        live_source_coverage=False,
        email_delivery_live=False,
        emails_sent=0,
    )


@router.get("/{org_id}/digest/readiness")
def get_digest_readiness(
    org_id: uuid.UUID,
    ctx: Annotated[OrgContext, Depends(require_demo_org_session)],
    db: Annotated[Session, Depends(get_db_session)],
) -> dict[str, Any]:
    """What is ready, and what is not, for this organization."""
    same_org(org_id, ctx)
    from nativeforge.services.tenant_digest_operational_readiness_service import (
        build_tenant_digest_readiness,
    )

    readiness = build_tenant_digest_readiness(
        connection=db.connection(), organization_id=str(org_id)
    )
    return envelope(
        {
            "organization_id": str(org_id),
            **{
                key: readiness[key]
                for key in (
                    "tenant_digest_operational",
                    "scope",
                    "profile_available",
                    "watchlist_available",
                    "digest_preview_available",
                    "weekly_default_available",
                    "daily_setting_available",
                    "suppression_available",
                    "source_monitoring_required_for_preview",
                    "email_required_for_preview",
                    "source_monitoring_live",
                    "email_delivery_available",
                    "production_tenant_digest",
                    "blocked_reasons",
                )
            },
        }
    )


@router.post("/{org_id}/digest/cadence")
def set_digest_cadence(
    org_id: uuid.UUID,
    body: CadenceBody,
    ctx: Annotated[OrgContext, Depends(require_demo_org_session)],
    db: Annotated[Session, Depends(get_db_session)],
) -> dict[str, Any]:
    """Enable or disable the daily alert, by writing the profile.

    An upsert, because that is what the profile repository offers: it archives
    the previous profile and inserts, so the change is visible in the history
    rather than overwriting what the tenant used to have chosen.
    """
    same_org(org_id, ctx)
    refuse_caller_supplied(body)

    from nativeforge.services.tenant_profile_repository_service import (
        get_tenant_profile,
        upsert_tenant_profile,
    )

    existing = get_tenant_profile(
        connection=db.connection(), organization_id=str(org_id)
    )
    if not existing.get("rows_read"):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "no_tenant_profile_for_this_organization"},
        )

    # Every other fact carried forward. A cadence change is not a reason to
    # lose a tenant's recognition status or its operating states.
    carried = {
        key: existing.get(key)
        for key in (
            "tenant_id_label",
            "customer_org_id_label",
            "recognition_status",
            "recognition_status_fact_status",
            "operating_states",
            "operating_states_fact_status",
            "applicant_classes",
            "applicant_classes_fact_status",
            "service_area",
            "programs",
            "departments",
            "priority_topics",
            "excluded_topics",
            "source_watchlist_preferences",
            "routing_rules",
            "custom_alerts",
            "profile_status",
        )
        if existing.get(key) is not None
    }

    result = upsert_tenant_profile(
        connection=db.connection(),
        organization_id=str(org_id),
        digest_frequency=body.digest_frequency,
        updated_by_identity_id=accountable_identity(db, org_id),
        is_demo=True,
        **carried,
    )
    refuse_if_blocked(result, wrote="digest_cadence")
    db.commit()
    return envelope(
        {
            "organization_id": str(org_id),
            "digest_frequency": result.get("digest_frequency"),
            "daily_alerts_enabled": result.get("digest_frequency") == "daily",
            "rows_written": int(result["rows_written"]),
        },
        emails_sent=0,
    )


@router.post("/{org_id}/digest/suppress", status_code=status.HTTP_201_CREATED)
def suppress_from_digest(
    org_id: uuid.UUID,
    body: SuppressBody,
    ctx: Annotated[OrgContext, Depends(require_demo_org_session)],
    db: Annotated[Session, Depends(get_db_session)],
) -> dict[str, Any]:
    """Hide one opportunity from the new-opportunity digest.

    The audit row goes first. `tenant_pursuit_suppression_service` refuses a
    suppression without an `audit_event_id`, and that refusal is the reason
    this route appends a real `nf_audit_events` row rather than minting an id:
    a suppression nobody can trace is a way for things to quietly stop
    appearing.
    """
    same_org(org_id, ctx)
    refuse_caller_supplied(body)
    identity = accountable_identity(db, org_id)

    audit = append_org_audit_event(
        db,
        organization_id=org_id,
        is_demo=True,
        action=AuditAction.grant_pursuit_updated,
        payload={
            "event": "suppressed_from_new_opportunity_digest",
            "opportunity_id": body.opportunity_id,
            "suppression_reason": body.suppression_reason,
            "pursuit_record_id": body.pursuit_record_id,
            "source_record_deleted": False,
            "provenance_preserved": True,
        },
        actor_id=uuid.UUID(identity),
    )
    db.flush()

    result = supp.record_suppression(
        connection=db.connection(),
        organization_id=str(org_id),
        opportunity_id=body.opportunity_id,
        suppression_reason=body.suppression_reason,
        pursuit_record_id=body.pursuit_record_id,
        audit_event_id=str(audit.id),
        created_by_identity_id=identity,
        fact_status="demo_fixture",
        is_demo=True,
    )
    # If the suppression is refused, the audit row must not stand either -
    # an audit event for something that did not happen is worse than none.
    if not result["rows_written"]:
        db.rollback()
    refuse_if_blocked(result, wrote="digest_suppression")
    db.commit()

    return envelope(
        {
            "organization_id": str(org_id),
            "opportunity_id": result.get("opportunity_id"),
            "suppression_status": result.get("suppression_status"),
            "suppression_reason": result.get("suppression_reason"),
            "audit_event_id": str(audit.id),
            "rows_written": int(result["rows_written"]),
            "rows_deleted": 0,
        },
        source_history_preserved=True,
        provenance_preserved=True,
        opportunity_deleted=False,
    )


@router.post("/{org_id}/digest/lift")
def lift_digest_suppression(
    org_id: uuid.UUID,
    body: LiftBody,
    ctx: Annotated[OrgContext, Depends(require_demo_org_session)],
    db: Annotated[Session, Depends(get_db_session)],
) -> dict[str, Any]:
    """Stop hiding it. Sets `lifted_at`; deletes nothing."""
    same_org(org_id, ctx)
    refuse_caller_supplied(body)

    result = supp.lift_suppression(
        connection=db.connection(),
        organization_id=str(org_id),
        opportunity_id=body.opportunity_id,
    )
    refuse_if_blocked(result, wrote="digest_suppression_lift")
    db.commit()
    return envelope(
        {
            "organization_id": str(org_id),
            "opportunity_id": result.get("opportunity_id"),
            "lifted": True,
            "rows_written": int(result["rows_written"]),
            "rows_deleted": 0,
        },
        source_history_preserved=True,
    )
