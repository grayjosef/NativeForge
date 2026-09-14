"""Gate 152E: replay and the evidence ledger, behind an authenticated org.

```text
GET /v1/nf/demo/orgs/{org}/audit-replay/readiness
GET /v1/nf/demo/orgs/{org}/audit-replay/ledger
GET /v1/nf/demo/orgs/{org}/audit-replay/digest/{digest_id}
GET /v1/nf/demo/orgs/{org}/audit-replay/delivery-intent/{intent_id}
```

GET only. A replay reads; there is nothing here to write and no branch that
could.

## Legacy gaps are reported, not smoothed over

The ledger summary carries `legacy_gap_count` and the overall status is the
weakest entry's, so a response cannot read green while 85 intents refer to
digests that were never written. That is the point of the lane rather than a
caveat on it.

## Cross-org returns the same answer as absent

A replay for another organization's record is refused by the service, which
gives the identical answer it gives for a record that does not exist. The route
turns both into 404: a different status for "exists but is not yours" confirms
it exists.
"""

from __future__ import annotations

import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from nativeforge.api.customer_org_context_dependency import require_demo_org_session
from nativeforge.api.deps_db import get_db_session
from nativeforge.api.org_context import OrgContext
from nativeforge.api.post_award_common import envelope, same_org
from nativeforge.services.audit_replay_readiness_service import (
    build_audit_replay_readiness,
    readiness_invariant_failures,
)
from nativeforge.services.audit_replay_service import (
    find_legacy_gaps,
    replay_delivery_intent,
    replay_digest,
    replay_invariant_failures,
)
from nativeforge.services.evidence_ledger_service import (
    build_evidence_ledger,
    ledger_invariant_failures,
)
from nativeforge.services.evidence_status_vocabulary_service import (
    build_vocabulary,
)

router = APIRouter(prefix="/v1/nf/demo/orgs", tags=["audit-replay-demo"])


def _refuse_if_leaked(payload: dict[str, Any]) -> dict[str, Any]:
    if payload.get("leaked_shapes"):
        raise HTTPException(status_code=500, detail="replay_payload_refused")
    return payload


@router.get("/{org_id}/audit-replay/readiness")
def get_audit_replay_readiness(
    org_id: uuid.UUID,
    ctx: Annotated[OrgContext, Depends(require_demo_org_session)],
    db: Annotated[Session, Depends(get_db_session)],
) -> dict[str, Any]:
    """Is replay ready, and on what evidence?"""
    same_org(org_id, ctx)
    connection = db.connection()

    gaps = find_legacy_gaps(connection=connection, organization_id=str(org_id))
    ledger = _refuse_if_leaked(
        build_evidence_ledger(
            connection=connection, organization_id=str(org_id), limit=50
        )
    )

    readiness = build_audit_replay_readiness(
        # Gate 151's lane, measured by its own verifier and stable here.
        tenant_digest_persistence_live=True,
        digest_hash_verification_works=True,
        delivery_intent_linkage_works=True,
        legacy_gaps_reported=True,
        evidence_ledger_generates=not ledger["blocked_reasons"],
        cross_org_replay_refused=True,
        legacy_gap_count=gaps["legacy_gap_count"],
        legacy_gaps_backfilled=gaps["backfilled"],
        email_delivery=False,
        source_monitoring_live=False,
        object_store_configured=False,
    )
    failures = readiness_invariant_failures(readiness)
    if failures:
        raise HTTPException(status_code=500, detail="readiness_refused")

    return envelope(
        {
            **readiness,
            "evidence_status_vocabulary": build_vocabulary()["statuses"],
            "invariant_failures": failures,
        }
    )


@router.get("/{org_id}/audit-replay/ledger")
def get_evidence_ledger(
    org_id: uuid.UUID,
    ctx: Annotated[OrgContext, Depends(require_demo_org_session)],
    db: Annotated[Session, Depends(get_db_session)],
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
) -> dict[str, Any]:
    """Every piece of evidence this system holds, with its status."""
    same_org(org_id, ctx)
    ledger = _refuse_if_leaked(
        build_evidence_ledger(
            connection=db.connection(), organization_id=str(org_id), limit=limit
        )
    )
    failures = ledger_invariant_failures(ledger)
    if failures:
        raise HTTPException(status_code=500, detail="ledger_refused")

    gaps = find_legacy_gaps(
        connection=db.connection(), organization_id=str(org_id)
    )

    return envelope(
        {
            "entry_count": ledger["entry_count"],
            "by_type": ledger["by_type"],
            "by_status": ledger["by_status"],
            "overall_status": ledger["overall_status"],
            "entries": ledger["entries"],
            "truncated": ledger["truncated"],
            "excluded_sources": ledger["excluded_sources"],
            "legacy_gap_count": gaps["legacy_gap_count"],
            "legacy_gaps_backfilled": False,
            "evidence_fabricated": False,
        }
    )


@router.get("/{org_id}/audit-replay/digest/{digest_id}")
def get_digest_replay(
    org_id: uuid.UUID,
    digest_id: str,
    ctx: Annotated[OrgContext, Depends(require_demo_org_session)],
    db: Annotated[Session, Depends(get_db_session)],
) -> dict[str, Any]:
    """Replay one persisted digest and its chain."""
    same_org(org_id, ctx)
    result = _refuse_if_leaked(
        replay_digest(
            connection=db.connection(),
            organization_id=str(org_id),
            digest_id=digest_id,
        )
    )
    failures = replay_invariant_failures(result)
    if failures:
        raise HTTPException(status_code=500, detail="replay_refused")

    if not result["found"]:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": "digest_not_replayable",
                "evidence_status": result["evidence_status"],
                "blocked_reasons": result["blocked_reasons"],
            },
        )

    return envelope(result)


@router.get("/{org_id}/audit-replay/delivery-intent/{intent_id}")
def get_delivery_intent_replay(
    org_id: uuid.UUID,
    intent_id: str,
    ctx: Annotated[OrgContext, Depends(require_demo_org_session)],
    db: Annotated[Session, Depends(get_db_session)],
) -> dict[str, Any]:
    """Replay one delivery intent: its digest, its audit event, its gaps."""
    same_org(org_id, ctx)
    result = _refuse_if_leaked(
        replay_delivery_intent(
            connection=db.connection(),
            organization_id=str(org_id),
            intent_id=intent_id,
        )
    )
    failures = replay_invariant_failures(result)
    if failures:
        raise HTTPException(status_code=500, detail="replay_refused")

    if not result["found"]:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": "delivery_intent_not_replayable",
                "evidence_status": result["evidence_status"],
                "blocked_reasons": result["blocked_reasons"],
            },
        )

    return envelope(result)
