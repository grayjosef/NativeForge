"""Gate 156H: scheduler health, jobs and blockers — and a dry-run evaluation.

```text
GET  /v1/nf/demo/orgs/{org}/source-scheduler/health
GET  /v1/nf/demo/orgs/{org}/source-scheduler/jobs
GET  /v1/nf/demo/orgs/{org}/source-scheduler/blockers
POST /v1/nf/demo/orgs/{org}/source-scheduler/dry-run
```

## The POST evaluates and returns. It does not run.

A POST here computes a cycle against a supplied clock and returns the counts.
It dispatches nothing, writes nothing, approves nothing and changes no
activation state. The method is POST because the caller supplies a clock and a
source list in a body, not because anything is mutated — and an invariant on
the cycle fails if `rows_written` is ever non-zero.

A route that could start collection would be a collection trigger reachable
with a session cookie. Gate 159 owns triggers, and it will not put one here.

## Runtime ready is not monitoring live

Every response carries `source_monitoring_live: false`, and it is a constant in
the health service with no branch that computes anything else. The point of
these routes is to let an operator see that a scheduler exists **and** that it
is refusing all 177 sources, at the same time.
"""

from __future__ import annotations

import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Body, Depends, HTTPException

from nativeforge.api.customer_org_context_dependency import require_demo_org_session
from nativeforge.api.org_context import OrgContext
from nativeforge.api.post_award_common import envelope, same_org
from nativeforge.services.source_collection_scheduler_health_service import (
    build_scheduler_health,
    scheduler_health_invariant_failures,
)
from nativeforge.services.source_collection_scheduler_loop_service import (
    cycle_invariant_failures,
    run_scheduler_cycle,
)
from nativeforge.services.source_monitoring_approved_source_service import (
    load_registry_rows,
)

router = APIRouter(prefix="/v1/nf/demo/orgs", tags=["source-scheduler-demo"])

#: The clock used when a caller supplies none. Fixed rather than `now()` so a
#: route response is reproducible and a test does not race the wall clock.
DEFAULT_EVALUATION_INSTANT = "2026-09-15T12:00:00Z"


def _registry_sources() -> list[dict[str, Any]]:
    """Every registry row, with every permission absent.

    The registry carries no terms column, no activation column and no human
    review column - which is precisely why Gate 143 reports all 177 rows as
    UNKNOWN, and UNKNOWN blocks. Nothing here supplies a value the registry
    does not have.
    """
    rows = load_registry_rows()
    return [
        {
            "source_id": key,
            "check_interval_days": None,
            "next_check_due_at": None,
            "last_checked_at": None,
            "is_enabled": True,
            "activation_state": "activation_blocked",
            "terms_state": "terms_unknown",
            "human_review_state": "human_review_required",
            "collector_registered": False,
            "known_source": True,
        }
        for key in sorted(rows)
    ]


def _cycle(now: Any = None, organization_id: Any = None) -> dict[str, Any]:
    cycle = run_scheduler_cycle(
        now=now or DEFAULT_EVALUATION_INSTANT,
        sources=_registry_sources(),
        organization_id=organization_id,
    )
    if cycle_invariant_failures(cycle):
        raise HTTPException(status_code=500, detail="scheduler_cycle_refused")
    return cycle


def _health(cycle: dict[str, Any]) -> dict[str, Any]:
    health = build_scheduler_health(
        cycle=cycle,
        # A scheduler PROCESS is Gate 157. A request cannot know, and does not
        # guess: None means nobody measured it.
        scheduler_process_active=None,
        persistent_state_available=True,
        activation_allowlist_count=0,
    )
    if scheduler_health_invariant_failures(health):
        raise HTTPException(status_code=500, detail="scheduler_health_refused")
    return health


@router.get("/{org_id}/source-scheduler/health")
def get_scheduler_health(
    org_id: uuid.UUID,
    ctx: Annotated[OrgContext, Depends(require_demo_org_session)],
) -> dict[str, Any]:
    """Does a scheduler runtime exist, and is anything permitted to run?"""
    same_org(org_id, ctx)
    health = _health(_cycle(organization_id=org_id))
    return envelope({**health, "invariant_failures": []})


@router.get("/{org_id}/source-scheduler/jobs")
def get_scheduler_jobs(
    org_id: uuid.UUID,
    ctx: Annotated[OrgContext, Depends(require_demo_org_session)],
) -> dict[str, Any]:
    """Every source as a job, with the reason each one refuses."""
    same_org(org_id, ctx)
    cycle = _cycle(organization_id=org_id)
    return envelope(
        {
            "jobs_known": cycle["jobs_known"],
            "jobs_due": cycle["jobs_due"],
            "jobs_executable": cycle["jobs_executable"],
            "jobs_refused": cycle["jobs_refused"],
            "jobs_by_state": cycle["jobs_by_state"],
            "jobs": cycle["jobs"],
            "collectors_invoked": 0,
            "live_source_calls": 0,
            "source_monitoring_live": False,
        }
    )


@router.get("/{org_id}/source-scheduler/blockers")
def get_scheduler_blockers(
    org_id: uuid.UUID,
    ctx: Annotated[OrgContext, Depends(require_demo_org_session)],
) -> dict[str, Any]:
    """Why nothing runs, counted by reason."""
    same_org(org_id, ctx)
    cycle = _cycle(organization_id=org_id)
    return envelope(
        {
            "refusal_reasons": cycle["refusal_reasons"],
            "distinct_refusal_reasons": cycle["distinct_refusal_reasons"],
            "jobs_refused": cycle["jobs_refused"],
            "jobs_executable": cycle["jobs_executable"],
            "activation_allowlist_count": 0,
            "what_would_have_to_change": [
                "a human reviews each source's terms of use",
                "an approver approves activation for a source",
                "a collector is registered for that source (Gate 161)",
                "a cadence is recorded for that source",
            ],
            "source_monitoring_live": False,
        }
    )


@router.post("/{org_id}/source-scheduler/dry-run")
def post_scheduler_dry_run(
    org_id: uuid.UUID,
    ctx: Annotated[OrgContext, Depends(require_demo_org_session)],
    body: Annotated[dict[str, Any] | None, Body()] = None,
) -> dict[str, Any]:
    """Evaluate a cycle against a supplied clock. Dispatches nothing."""
    same_org(org_id, ctx)
    payload = body or {}
    cycle = _cycle(now=payload.get("now"), organization_id=org_id)
    health = _health(cycle)

    return envelope(
        {
            "evaluated_at": cycle["evaluated_at"],
            "mode": cycle["mode"],
            "jobs_known": cycle["jobs_known"],
            "jobs_due": cycle["jobs_due"],
            "jobs_executable": cycle["jobs_executable"],
            "jobs_refused": cycle["jobs_refused"],
            "refusal_reasons": cycle["refusal_reasons"],
            "scheduler_runtime_ready": health["scheduler_runtime_ready"],
            "execution_modes_not_implemented": cycle["execution_modes_not_implemented"],
            # Constants. A dry run evaluates.
            "collectors_invoked": 0,
            "live_source_calls": 0,
            "network_calls": 0,
            "rows_written": 0,
            "activation_changed": False,
            "source_approved": False,
            "source_monitoring_live": False,
        }
    )
