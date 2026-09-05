"""Gate 142G: digest delivery, rehearsed behind an authenticated org context.

```text
GET  /v1/nf/demo/orgs/{org}/digest/delivery/preview     render, sent nowhere
GET  /v1/nf/demo/orgs/{org}/digest/delivery/recipients  fingerprints, no addresses
POST /v1/nf/demo/orgs/{org}/digest/delivery/dry-run     record intents, audited
GET  /v1/nf/demo/orgs/{org}/digest/delivery/intents     what was recorded
POST /v1/nf/demo/orgs/{org}/digest/delivery/cancel      withdraw one
GET  /v1/nf/demo/orgs/{org}/digest/delivery/readiness   what is and is not ready
```

## Nothing here sends

There is no provider, no client, no socket and no mail library imported by this
module or by any service it calls. Every response carries `emails_sent: 0`,
`provider_contacted: false` and `send_attempted: false`, and the database
CHECKs all three on every stored row.

## No address reaches a response

`/recipients` returns fingerprints and domains. The address exists only inside
`validate_recipient`, which reads it from `nf_identities` and returns a handle.
A route that echoed one back would have made the fingerprint pointless.

## The dry run writes an audit row first

Same shape Gate 140 used for suppression, and for the same reason: an intent
nobody can trace is a way for a system to quietly decide who gets mail. The
audit event is appended, flushed, and its id stored on the intent. If no intent
is written, the audit row is rolled back — an audit event for something that did
not happen is worse than none.
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
from nativeforge.services import digest_delivery_dry_run_queue_service as queue
from nativeforge.services.digest_delivery_renderer_service import (
    render_digest_for_delivery,
    render_invariant_failures,
)
from nativeforge.services.digest_recipient_validation_service import (
    resolve_org_recipients,
)
from nativeforge.services.tenant_nofo_digest_service import build_org_digest_preview

router = APIRouter(prefix="/v1/nf/demo/orgs", tags=["digest-delivery-demo"])

CADENCES = frozenset({"weekly", "daily"})


class DryRunBody(BaseModel):
    """Ask for a rehearsal. Nothing here names a recipient.

    Recipients come from the organization's own membership rows. A caller
    supplying one would be a caller choosing who gets mail, which is a decision
    this route does not accept.
    """

    cadence: str = Field(default="weekly", max_length=16)

    model_config = {"extra": "allow"}


class CancelBody(BaseModel):
    intent_id: str = Field(min_length=1, max_length=64)

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


def _render(db: Session, org_id: uuid.UUID, cadence: str) -> dict[str, Any]:
    """The digest, rendered. Refuses with the digest's own reasons."""
    preview = build_org_digest_preview(
        connection=db.connection(), organization_id=str(org_id), cadence=cadence
    )
    if preview["blocked_reasons"]:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "error": "digest_not_produced",
                "blocked_reasons": preview["blocked_reasons"],
                "cadence": cadence,
            },
        )
    render = render_digest_for_delivery(
        digest=preview, organization_label=f"organization {org_id}"
    )
    fails = render_invariant_failures(render)
    if fails:
        # A render invariant failure is a bug in the renderer, not a caller
        # error. Nothing the caller sent caused it.
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "render_invariant_failed", "failures": fails},
        )
    return render


@router.get("/{org_id}/digest/delivery/preview")
def get_delivery_preview(
    org_id: uuid.UUID,
    ctx: Annotated[OrgContext, Depends(require_demo_org_session)],
    db: Annotated[Session, Depends(get_db_session)],
    cadence: str = "weekly",
) -> dict[str, Any]:
    """What would be sent, if anything were sent. It is not."""
    same_org(org_id, ctx)
    _refuse_unknown_cadence(cadence)
    render = _render(db, org_id, cadence)

    return envelope(
        {
            "organization_id": str(org_id),
            "cadence": render["cadence"],
            "digest_period_key": render["digest_period_key"],
            "subject_line": render["subject_line"],
            "body_text": render["body_text"],
            "body_render_hash": render["body_render_hash"],
            "body_byte_length": render["body_byte_length"],
            "items_total": render["items_total"],
            "items_visible": render["items_visible"],
            "items_rendered": render["items_rendered"],
            "items_with_unresolved_eligibility": render[
                "items_with_unresolved_eligibility"
            ],
            "items_with_unverified_deadlines": render[
                "items_with_unverified_deadlines"
            ],
            "deliverable": render["deliverable"],
        },
        delivery_status="preview_only",
        email_delivery=False,
        emails_sent=0,
        send_attempted=False,
        provider_contacted=False,
        recipient_in_render=False,
    )


@router.get("/{org_id}/digest/delivery/recipients")
def get_delivery_recipients(
    org_id: uuid.UUID,
    ctx: Annotated[OrgContext, Depends(require_demo_org_session)],
    db: Annotated[Session, Depends(get_db_session)],
) -> dict[str, Any]:
    """Who a digest would go to, as fingerprints. No address is returned."""
    same_org(org_id, ctx)
    resolved = resolve_org_recipients(
        connection=db.connection(), organization_id=str(org_id)
    )
    return envelope(
        {
            "organization_id": str(org_id),
            "rows_read": resolved["rows_read"],
            "deliverable_count": resolved["deliverable_count"],
            "human_review_count": resolved["human_review_count"],
            "recipients": [
                {
                    "recipient_fingerprint": r["recipient_fingerprint"],
                    "recipient_domain": r["recipient_domain"],
                    "recipient_source": r["recipient_source"],
                    "recipient_verified": r["recipient_verified"],
                    "deliverable": r["deliverable"],
                    "blocked_reasons": r["blocked_reasons"],
                }
                for r in resolved["recipients"]
            ],
            "blocked_reasons": resolved["blocked_reasons"],
        },
        addresses_reported=False,
        addresses_stored=False,
        dns_checked=False,
        emails_sent=0,
    )


@router.post("/{org_id}/digest/delivery/dry-run", status_code=status.HTTP_201_CREATED)
def record_delivery_dry_run(
    org_id: uuid.UUID,
    body: DryRunBody,
    ctx: Annotated[OrgContext, Depends(require_demo_org_session)],
    db: Annotated[Session, Depends(get_db_session)],
) -> dict[str, Any]:
    """Record what would be delivered. Nothing is delivered.

    The audit row goes first and is rolled back if no intent is written: an
    audit event for something that did not happen is worse than none.
    """
    same_org(org_id, ctx)
    refuse_caller_supplied(body)
    cadence = str(body.cadence or "weekly").strip().lower()
    _refuse_unknown_cadence(cadence)

    render = _render(db, org_id, cadence)
    identity = accountable_identity(db, org_id)
    resolved = resolve_org_recipients(
        connection=db.connection(), organization_id=str(org_id)
    )
    if not resolved["recipients"]:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "error": "no_recipients_for_this_organization",
                "blocked_reasons": resolved["blocked_reasons"],
            },
        )

    from nativeforge.services.email_provider_configuration_preflight_service import (
        build_email_provider_preflight,
    )

    preflight = build_email_provider_preflight()

    audit = append_org_audit_event(
        db,
        organization_id=org_id,
        is_demo=True,
        action=AuditAction.digest_delivery_intent_recorded,
        payload={
            "event": "digest_delivery_dry_run",
            "cadence": cadence,
            "digest_period_key": render["digest_period_key"],
            # Counts and a hash. No address and no body.
            "recipient_count": len(resolved["recipients"]),
            "deliverable_recipient_count": resolved["deliverable_count"],
            "body_render_hash": render["body_render_hash"],
            "emails_sent": 0,
            "send_attempted": False,
            "provider_contacted": False,
        },
        actor_id=uuid.UUID(identity),
    )
    db.flush()

    recorded: list[dict[str, Any]] = []
    written = 0
    for recipient in resolved["recipients"]:
        result = queue.record_delivery_intent(
            connection=db.connection(),
            organization_id=str(org_id),
            digest_period_key=render["digest_period_key"],
            cadence=render["cadence"],
            recipient_fingerprint=recipient["recipient_fingerprint"],
            recipient_domain=recipient["recipient_domain"],
            recipient_source=recipient["recipient_source"],
            recipient_verified=recipient["recipient_verified"],
            subject_line=render["subject_line"],
            body_render_hash=render["body_render_hash"],
            body_byte_length=render["body_byte_length"],
            items_total=render["items_total"],
            items_visible=render["items_visible"],
            digest_deliverable=render["deliverable"],
            send_activated=preflight["send_activated"],
            provider_configured=preflight["provider_configured"],
            digest_id=render["digest_period_key"],
            audit_event_id=str(audit.id),
            created_by_identity_id=identity,
            fact_status="demo_fixture",
            is_demo=True,
        )
        written += int(result["rows_written"])
        recorded.append(
            {
                "intent_id": result["intent_id"],
                "recipient_fingerprint": result["recipient_fingerprint"],
                "recipient_domain": result["recipient_domain"],
                "delivery_status": result["delivery_status"],
                "blocked_reason": result["blocked_reason"],
                "rows_written": int(result["rows_written"]),
                "blocked_reasons": result["blocked_reasons"],
            }
        )

    if not written:
        # Nothing was recorded, so the audit row must not stand either.
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "error": "no_delivery_intent_was_recorded",
                "intents": recorded,
                "emails_sent": 0,
            },
        )
    db.commit()

    return envelope(
        {
            "organization_id": str(org_id),
            "cadence": cadence,
            "digest_period_key": render["digest_period_key"],
            "audit_event_id": str(audit.id),
            "intents": recorded,
            "rows_written": written,
            "rows_deleted": 0,
            "preflight_state": preflight["state"],
            "send_disabled_reason": (
                recorded[0]["blocked_reason"] if recorded else None
            ),
            "missing_configuration": preflight["absent_setting_names"],
        },
        delivery_status="dry_run_recorded",
        email_delivery=False,
        emails_sent=0,
        send_attempted=False,
        provider_contacted=False,
        addresses_stored=False,
    )


@router.get("/{org_id}/digest/delivery/intents")
def list_delivery_intents(
    org_id: uuid.UUID,
    ctx: Annotated[OrgContext, Depends(require_demo_org_session)],
    db: Annotated[Session, Depends(get_db_session)],
    include_cancelled: bool = False,
) -> dict[str, Any]:
    same_org(org_id, ctx)
    result = queue.list_delivery_intents(
        connection=db.connection(),
        organization_id=str(org_id),
        include_cancelled=include_cancelled,
    )
    return envelope(
        {
            "organization_id": str(org_id),
            "rows_read": result["rows_read"],
            "intents": result["intents"],
            "dry_run_recorded_count": result["dry_run_recorded_count"],
            "send_disabled_count": result["send_disabled_count"],
            "refused_count": result["refused_count"],
        },
        emails_sent=0,
        provider_contacted=False,
        addresses_stored=False,
    )


@router.post("/{org_id}/digest/delivery/cancel")
def cancel_delivery_intent(
    org_id: uuid.UUID,
    body: CancelBody,
    ctx: Annotated[OrgContext, Depends(require_demo_org_session)],
    db: Annotated[Session, Depends(get_db_session)],
) -> dict[str, Any]:
    """Withdraw an intent. Sets `cancelled_at`; deletes nothing."""
    same_org(org_id, ctx)
    refuse_caller_supplied(body)
    result = queue.cancel_delivery_intent(
        connection=db.connection(),
        organization_id=str(org_id),
        intent_id=body.intent_id,
    )
    refuse_if_blocked(result, wrote="digest_delivery_intent_cancel")
    db.commit()
    return envelope(
        {
            "organization_id": str(org_id),
            "intent_id": result["intent_id"],
            "cancelled": True,
            "rows_written": int(result["rows_written"]),
            "rows_deleted": 0,
        },
        emails_sent=0,
    )


@router.get("/{org_id}/digest/delivery/readiness")
def get_delivery_readiness(
    org_id: uuid.UUID,
    ctx: Annotated[OrgContext, Depends(require_demo_org_session)],
    db: Annotated[Session, Depends(get_db_session)],
) -> dict[str, Any]:
    """What is ready to rehearse, and what would activation still need."""
    same_org(org_id, ctx)

    from nativeforge.services.email_delivery_readiness_service import (
        build_email_delivery_readiness,
    )
    from nativeforge.services.email_provider_configuration_preflight_service import (
        build_email_provider_preflight,
    )

    preflight = build_email_provider_preflight()
    stored = queue.list_delivery_intents(
        connection=db.connection(), organization_id=str(org_id)
    )
    readiness = build_email_delivery_readiness(preflight=preflight)

    return envelope(
        {
            "organization_id": str(org_id),
            "email_delivery_readiness": readiness["email_delivery_readiness"],
            "email_delivery": readiness["email_delivery"],
            "scope": readiness["scope"],
            "preflight_state": preflight["state"],
            "provider_configured": preflight["provider_configured"],
            "send_activated": preflight["send_activated"],
            # Setting NAMES, never values.
            "missing_configuration": preflight["absent_setting_names"],
            "provider_required_for_readiness": readiness[
                "provider_required_for_readiness"
            ],
            "send_activation_required_for_readiness": readiness[
                "send_activation_required_for_readiness"
            ],
            "recorded_intents": stored["rows_read"],
            "send_disabled_count": stored["send_disabled_count"],
            "blocked_reasons": readiness["blocked_reasons"],
        },
        email_delivery=False,
        emails_sent=0,
        provider_contacted=False,
        production_email_delivery=False,
    )
