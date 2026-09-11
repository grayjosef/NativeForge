"""Gate 145C: the controlled beta decision, behind an authenticated org context.

```text
GET /v1/nf/demo/orgs/{org}/beta-decision/readiness     three scopes, decided
GET /v1/nf/demo/orgs/{org}/beta-decision/blockers      what stops each
GET /v1/nf/demo/orgs/{org}/beta-decision/unsafe-claims  what not to say
GET /v1/nf/demo/orgs/{org}/beta-decision/approvals      who has to decide what
```

## It decides nothing and approves nothing

These routes report a decision computed from measured facts. Reading one does
not activate a pilot, and there is no route here that could — `controlled_
customer_pilot` and `production_rollout` have no branch anywhere in this
codebase that sets them.

## It measures what a request can measure

The same rule Gate 144 established: a request proves what a request can prove.
It runs the persistence round trip for real and reads the capability flags from
their own services; the lanes needing a route smoke are supplied by whoever ran
the verifiers, and are absent here rather than assumed.

## Nothing is activated

No live source is called, no collector starts, no mail is sent, no object store
is contacted, no real customer data is written, and the real organization is
never addressed.
"""

from __future__ import annotations

import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from nativeforge.api.customer_org_context_dependency import require_demo_org_session
from nativeforge.api.deps_db import get_db_session
from nativeforge.api.org_context import OrgContext
from nativeforge.api.post_award_common import envelope, same_org
from nativeforge.services.controlled_beta_readiness_decision_service import (
    CONFLATIONS,
    HUMAN_APPROVALS,
    SCOPES,
    TECHNICAL_BLOCKERS,
    UNSAFE_CLAIMS,
    build_controlled_beta_decision,
    decision_invariant_failures,
)

router = APIRouter(prefix="/v1/nf/demo/orgs", tags=["controlled-beta-decision-demo"])


def _decision(db: Session, org_id: uuid.UUID) -> dict[str, Any]:
    """The decision, from what this request can actually measure."""
    from nativeforge.services.customer_persistence_activation_service import (
        prove_customer_persistence,
    )
    from nativeforge.services.source_collector_configuration_preflight_service import (
        build_collector_preflight,
    )
    from nativeforge.services.source_monitoring_readiness_service import (
        build_source_monitoring_readiness,
    )
    from nativeforge.services.tenant_source_watchlist_service import (
        known_registry_source_ids,
    )

    connection = db.connection()
    persistence = prove_customer_persistence(
        connection=connection, organization_id=str(org_id)
    )
    known = known_registry_source_ids()
    monitoring = build_source_monitoring_readiness(
        collector_preflight=build_collector_preflight(
            config={
                "source_id": next(iter(sorted(known))) if known else "",
                "fetch_mode": "dry_run",
                "rate_limit_policy": "polite_default",
                "attribution_requirement": "not_required",
                "user_agent_policy": "nativeforge_canonical",
                "raw_payload_storage_policy": "local_dev_ignored",
                "activation_approval": False,
            }
        ),
        watchlist_can_name_sources=bool(known),
        tenant_digest_operational=True,
    )

    return build_controlled_beta_decision(
        customer_persistence_live=bool(persistence["customer_persistence_live"]),
        source_monitoring_preflight_ready=bool(
            monitoring["source_monitoring_preflight_ready"]
        ),
        beta_onboarding_cockpit_route_live=True,
        # Everything else needs a route smoke this request cannot honestly run,
        # and is therefore absent rather than assumed.
    )


@router.get("/{org_id}/beta-decision/readiness")
def get_beta_decision(
    org_id: uuid.UUID,
    ctx: Annotated[OrgContext, Depends(require_demo_org_session)],
    db: Annotated[Session, Depends(get_db_session)],
) -> dict[str, Any]:
    """Three scopes, three decisions, each with its conditions and constraints."""
    same_org(org_id, ctx)
    decision = _decision(db, org_id)

    return envelope(
        {
            "organization_id": str(org_id),
            "scopes": decision["scopes"],
            "by_scope": decision["by_scope"],
            "internal_demo_beta": decision["internal_demo_beta"],
            "controlled_customer_beta": decision["controlled_customer_beta"],
            "production_rollout": decision["production_rollout"],
            "measured_capabilities": decision["measured_capabilities"],
            "conflations": decision["conflations"],
            "invariant_failures": decision_invariant_failures(decision),
        },
        controlled_customer_pilot_activated=False,
        production_approved=False,
        customer_auth_live=False,
        source_monitoring_live=False,
        email_delivery=False,
        object_store_configured=False,
        live_source_calls=0,
        emails_sent=0,
        object_store_calls=0,
        collectors_activated=0,
        real_customer_data_written=False,
    )


@router.get("/{org_id}/beta-decision/blockers")
def get_beta_decision_blockers(
    org_id: uuid.UUID,
    ctx: Annotated[OrgContext, Depends(require_demo_org_session)],
    db: Annotated[Session, Depends(get_db_session)],
) -> dict[str, Any]:
    """What stops each scope, separated into decisions and code."""
    same_org(org_id, ctx)
    decision = _decision(db, org_id)

    return envelope(
        {
            "organization_id": str(org_id),
            "by_scope": {
                scope: {
                    "decision": entry["decision"],
                    "blockers": entry["blockers"],
                    "conditions_missing": entry["conditions_missing"],
                }
                for scope, entry in decision["by_scope"].items()
            },
            # Separated on purpose: an operator reading a blocker needs to know
            # whether to write code or to make a decision.
            "technical_blockers": list(TECHNICAL_BLOCKERS),
            "human_approvals_required": [a["approval"] for a in HUMAN_APPROVALS],
        },
        production_approved=False,
        controlled_customer_pilot_activated=False,
        live_source_calls=0,
        emails_sent=0,
    )


@router.get("/{org_id}/beta-decision/unsafe-claims")
def get_beta_decision_unsafe_claims(
    org_id: uuid.UUID,
    ctx: Annotated[OrgContext, Depends(require_demo_org_session)],
) -> dict[str, Any]:
    """Sentences that would be false today, each paired with a true one.

    Named so they can be refused rather than discovered. Every one is something
    somebody could reasonably say after reading a green cockpit.
    """
    same_org(org_id, ctx)

    return envelope(
        {
            "organization_id": str(org_id),
            "unsafe_claims": list(UNSAFE_CLAIMS),
            "unsafe_claim_count": len(UNSAFE_CLAIMS),
            "conflations": list(CONFLATIONS),
            "conflation_count": len(CONFLATIONS),
        },
        production_approved=False,
        improvement_claims=[],
        customer_names_reported=False,
    )


@router.get("/{org_id}/beta-decision/approvals")
def get_beta_decision_approvals(
    org_id: uuid.UUID,
    ctx: Annotated[OrgContext, Depends(require_demo_org_session)],
) -> dict[str, Any]:
    """Who has to decide what, and why no code change does it for them."""
    same_org(org_id, ctx)

    return envelope(
        {
            "organization_id": str(org_id),
            "human_approvals": list(HUMAN_APPROVALS),
            "approval_count": len(HUMAN_APPROVALS),
            "scopes": list(SCOPES),
            "none_of_these_is_automatable": True,
        },
        production_approved=False,
        controlled_customer_pilot_activated=False,
        approvals_granted_by_this_route=0,
    )
