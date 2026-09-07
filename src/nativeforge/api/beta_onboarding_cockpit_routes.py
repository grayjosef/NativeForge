"""Gate 144C: the beta onboarding cockpit, behind an authenticated org context.

```text
GET /v1/nf/demo/orgs/{org}/beta-cockpit/readiness      every lane, measured
GET /v1/nf/demo/orgs/{org}/beta-cockpit/next-actions    the one safe next step
GET /v1/nf/demo/orgs/{org}/beta-cockpit/blockers        why each lane is blocked
GET /v1/nf/demo/orgs/{org}/beta-cockpit/capabilities    what the demo org can do
```

## It reports the deployment, not a tenant

No route here reads a Tribe's name, a grant, an eligibility or a deadline. The
cockpit answers "what can this deployment do", which is a different question
from "what is in this customer's pipeline" — and a far safer one to put on a
screen.

## It measures rather than assuming

Several readiness services take injectable proofs so their permitted branches
stay reachable. A cockpit that supplied those proofs itself would be grading its
own homework. So these routes run the **lanes that can establish themselves** —
persistence with a real round trip, the digest with the organization's own rows —
and report `readiness_only` for anything needing evidence a request cannot
honestly produce.

## Nothing here activates anything

No live source is called, no collector starts, no mail is sent, no object store
is contacted, and no lane's value is changed. Every response says so.
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
from nativeforge.services.beta_onboarding_readiness_summary_service import (
    LANE_KEYS,
    LANE_STATUSES,
    NOT_APPROVED,
    build_beta_onboarding_summary,
    summary_invariant_failures,
)

router = APIRouter(prefix="/v1/nf/demo/orgs", tags=["beta-onboarding-cockpit-demo"])


def _measured(db: Session, org_id: uuid.UUID) -> dict[str, Any]:
    """The lanes this request can establish, measured against real rows.

    Each is a fact the request can actually check. Anything else is left
    unsupplied so the summary reports `readiness_only` rather than a guess.
    """
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

    # Gate 138's round trip, run for real: write, read back by id, archive.
    persistence = prove_customer_persistence(
        connection=connection, organization_id=str(org_id)
    )

    # Gate 143's preflight, which establishes itself given a collector config.
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

    return {
        "customer_persistence_live": bool(persistence["customer_persistence_live"]),
        "source_monitoring_preflight_ready": bool(
            monitoring["source_monitoring_preflight_ready"]
        ),
        "persistence_rows_left_live": int(persistence["rows_left_live"]),
    }


def _summary(db: Session, org_id: uuid.UUID, **supplied: Any) -> dict[str, Any]:
    measured = _measured(db, org_id)
    return build_beta_onboarding_summary(
        customer_persistence_live=measured["customer_persistence_live"],
        source_monitoring_preflight_ready=measured["source_monitoring_preflight_ready"],
        **supplied,
    )


@router.get("/{org_id}/beta-cockpit/readiness")
def get_cockpit_readiness(
    org_id: uuid.UUID,
    ctx: Annotated[OrgContext, Depends(require_demo_org_session)],
    db: Annotated[Session, Depends(get_db_session)],
) -> dict[str, Any]:
    """Every lane, with its status, its value and what blocks it."""
    same_org(org_id, ctx)
    summary = _summary(db, org_id)

    return envelope(
        {
            "organization_id": str(org_id),
            "cockpit_scope": summary["scope"],
            "lane_keys": summary["lane_keys"],
            "lane_statuses": summary["lane_statuses"],
            "lanes": summary["lanes"],
            "operational_lanes": summary["operational_lanes"],
            "blocked_lanes": summary["blocked_lanes"],
            "requires_human_approval_lanes": summary["requires_human_approval_lanes"],
            "not_configured_lanes": summary["not_configured_lanes"],
            "usable_today_count": summary["usable_today_count"],
            "invariant_failures": summary_invariant_failures(summary),
        },
        # Every one of these is a claim the cockpit does not make.
        production_rollout=False,
        controlled_customer_pilot=False,
        customer_auth_live=False,
        source_monitoring_live=False,
        email_delivery=False,
        object_store_configured=False,
        verified_operational_binding=False,
        live_source_calls=0,
        emails_sent=0,
        object_store_calls=0,
        collectors_activated=0,
        customer_names_reported=False,
    )


@router.get("/{org_id}/beta-cockpit/next-actions")
def get_cockpit_next_actions(
    org_id: uuid.UUID,
    ctx: Annotated[OrgContext, Depends(require_demo_org_session)],
    db: Annotated[Session, Depends(get_db_session)],
) -> dict[str, Any]:
    """The one thing that is safe to do next, and what is deliberately not."""
    same_org(org_id, ctx)
    summary = _summary(db, org_id)
    action = summary["next_safe_action"]

    return envelope(
        {
            "organization_id": str(org_id),
            "next_safe_action": action["action"],
            "why": action["why"],
            "safe_because": action["safe_because"],
            "not_this_yet": action["not_this_yet"],
            "operational_lanes": summary["operational_lanes"],
            "requires_human_approval_lanes": summary["requires_human_approval_lanes"],
        },
        production_rollout=False,
        controlled_customer_pilot=False,
        activates_nothing=True,
        live_source_calls=0,
        emails_sent=0,
    )


@router.get("/{org_id}/beta-cockpit/blockers")
def get_cockpit_blockers(
    org_id: uuid.UUID,
    ctx: Annotated[OrgContext, Depends(require_demo_org_session)],
    db: Annotated[Session, Depends(get_db_session)],
) -> dict[str, Any]:
    """Why each lane that is not operational is not, and who owns it."""
    same_org(org_id, ctx)
    summary = _summary(db, org_id)

    blockers = [
        {
            "lane": lane["lane"],
            "status": lane["status"],
            "blockers": lane["blockers"],
            "owner": lane["owner"],
            "summary": lane["summary"],
        }
        for lane in summary["lanes"]
        if lane["blockers"]
    ]

    return envelope(
        {
            "organization_id": str(org_id),
            "blockers": blockers,
            "blocked_lane_count": len(blockers),
            "requires_human_approval_lanes": summary["requires_human_approval_lanes"],
            "not_configured_lanes": summary["not_configured_lanes"],
            "not_approved": list(NOT_APPROVED),
        },
        production_rollout=False,
        controlled_customer_pilot=False,
        live_source_calls=0,
        emails_sent=0,
    )


@router.get("/{org_id}/beta-cockpit/capabilities")
def get_cockpit_capabilities(
    org_id: uuid.UUID,
    ctx: Annotated[OrgContext, Depends(require_demo_org_session)],
    db: Annotated[Session, Depends(get_db_session)],
) -> dict[str, Any]:
    """What this demo organization can actually do today, lane by lane.

    A capability matrix rather than a score: "7 of 15" would tell an operator
    nothing about which seven, and the seven that are missing are the ones that
    need a decision.
    """
    same_org(org_id, ctx)
    summary = _summary(db, org_id)

    return envelope(
        {
            "organization_id": str(org_id),
            "scope": summary["scope"],
            "capabilities": [
                {
                    "lane": lane["lane"],
                    "status": lane["status"],
                    "usable_today": lane["usable_today"],
                    "evidence": lane["evidence"],
                    "summary": lane["summary"],
                }
                for lane in summary["lanes"]
            ],
            "usable_today_count": summary["usable_today_count"],
            "total_lane_count": len(LANE_KEYS),
            "lane_statuses": list(LANE_STATUSES),
        },
        production_rollout=False,
        controlled_customer_pilot=False,
        real_organization_touched=False,
        customer_names_reported=False,
        eligibility_reported=False,
        deadlines_reported=False,
    )
