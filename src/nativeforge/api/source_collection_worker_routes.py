"""Gate 157H: worker health, jobs and leases — and a dry-run cycle.

```text
GET  /v1/nf/demo/orgs/{org}/source-worker/health
GET  /v1/nf/demo/orgs/{org}/source-worker/jobs
GET  /v1/nf/demo/orgs/{org}/source-worker/leases
POST /v1/nf/demo/orgs/{org}/source-worker/dry-run
```

## The POST claims nothing and writes nothing

Gate 156's dry-run route computes a scheduler cycle. This one computes a
**worker** cycle in memory and returns the counts — with no connection passed,
so no lease is taken and no row is written. The worker runtime refuses outright
without a connection, which is what makes that safe rather than merely intended.

Claiming a lease from a request would let anyone with a session cookie take a
claim a real worker then could not have, and lease expiry would be the only
thing releasing it.

## Leases are read, never swept

The GET returns lease rows as they are, including stale ones. Nothing here
expires, releases or reclaims a lease: a sweeper is a scheduled job and Gate 159
owns triggers.

## Worker ready is not monitoring live

Every response carries `source_monitoring_live: false`, constant in the health
service. With zero approved sources every job refuses, and the refusal reason is
on every row.
"""

from __future__ import annotations

import uuid
from typing import Annotated, Any

import sqlalchemy as sa
from fastapi import APIRouter, Body, Depends, HTTPException
from sqlalchemy.orm import Session

from nativeforge.api.customer_org_context_dependency import require_demo_org_session
from nativeforge.api.deps_db import get_db_session
from nativeforge.api.org_context import OrgContext
from nativeforge.api.post_award_common import envelope, same_org
from nativeforge.services.source_collection_job_lease_service import (
    LEASES,
)
from nativeforge.services.source_collection_scheduler_loop_service import (
    run_scheduler_cycle,
)
from nativeforge.services.source_collection_worker_health_service import (
    build_worker_health,
    worker_health_invariant_failures,
)
from nativeforge.services.source_collection_worker_runtime_service import (
    run_worker_cycle,
    worker_cycle_invariant_failures,
)
from nativeforge.services.source_monitoring_approved_source_service import (
    load_registry_rows,
)

router = APIRouter(prefix="/v1/nf/demo/orgs", tags=["source-worker-demo"])

#: Fixed so a response is reproducible and a test does not race the clock.
DEFAULT_EVALUATION_INSTANT = "2026-09-15T12:00:00Z"


def _scheduler_jobs(now: str) -> list[dict[str, Any]]:
    rows = load_registry_rows()
    return run_scheduler_cycle(
        now=now,
        sources=[
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
            }
            for key in sorted(rows)
        ],
    )["jobs"]


def _in_memory_cycle(now: str, org_id: uuid.UUID) -> dict[str, Any]:
    """A cycle with NO connection: nothing is claimed and nothing is written."""
    cycle = run_worker_cycle(
        connection=None,
        organization_id=str(org_id),
        worker_id="nf-worker-route-dry-run",
        jobs=_scheduler_jobs(now),
        now=now,
    )
    # Without a connection the runtime refuses outright, which is the point:
    # a route cannot take a lease even by accident.
    return cycle


def _stale_lease_count(db: Session, org_id: uuid.UUID, now: str) -> int:
    moment = sa.literal(now)
    try:
        return int(
            db.connection()
            .execute(
                sa.select(sa.func.count())
                .select_from(LEASES)
                .where(
                    sa.and_(
                        LEASES.c.organization_id == org_id,
                        LEASES.c.lease_owner.isnot(None),
                        LEASES.c.lease_expires_at.isnot(None),
                        LEASES.c.lease_expires_at <= moment,
                    )
                )
            )
            .scalar()
            or 0
        )
    except Exception:  # noqa: BLE001 - a health read that 500s is worse
        return 0


@router.get("/{org_id}/source-worker/health")
def get_worker_health(
    org_id: uuid.UUID,
    ctx: Annotated[OrgContext, Depends(require_demo_org_session)],
    db: Annotated[Session, Depends(get_db_session)],
) -> dict[str, Any]:
    """Does a worker runtime exist, and has anything been permitted to run?"""
    same_org(org_id, ctx)
    jobs = _scheduler_jobs(DEFAULT_EVALUATION_INSTANT)
    health = build_worker_health(
        # A request does not run a cycle against the database, so the lane's
        # conditions are not measured here. The verifier measures them.
        cycle=None,
        worker_process_active=None,
        jobs_available=len(jobs),
        jobs_claimable=sum(1 for job in jobs if job.get("executable")),
        stale_leases=_stale_lease_count(db, org_id, DEFAULT_EVALUATION_INSTANT),
        activation_allowlist_count=0,
    )
    failures = worker_health_invariant_failures(health)
    if failures:
        raise HTTPException(status_code=500, detail="worker_health_refused")

    return envelope(
        {
            **health,
            "measured_by_the_verifier": [
                "cycle_completed",
                "claim_is_atomic",
                "expired_lease_reclaimed",
                "retries_are_bounded",
            ],
            "why": (
                "a request does not claim leases, so the conditions that need a "
                "real claim are measured by "
                "scripts/verify_nativeforge_source_worker_runtime.sh"
            ),
            "invariant_failures": failures,
        }
    )


@router.get("/{org_id}/source-worker/jobs")
def get_worker_jobs(
    org_id: uuid.UUID,
    ctx: Annotated[OrgContext, Depends(require_demo_org_session)],
) -> dict[str, Any]:
    """What a worker would be offered, and how much it would refuse."""
    same_org(org_id, ctx)
    jobs = _scheduler_jobs(DEFAULT_EVALUATION_INSTANT)
    return envelope(
        {
            "jobs_available": len(jobs),
            "jobs_claimable": sum(1 for job in jobs if job.get("executable")),
            "jobs_would_refuse": sum(1 for job in jobs if not job.get("executable")),
            "jobs": jobs[:50],
            "truncated": len(jobs) > 50,
            "collectors_invoked": 0,
            "live_source_calls": 0,
            "source_monitoring_live": False,
        }
    )


@router.get("/{org_id}/source-worker/leases")
def get_worker_leases(
    org_id: uuid.UUID,
    ctx: Annotated[OrgContext, Depends(require_demo_org_session)],
    db: Annotated[Session, Depends(get_db_session)],
) -> dict[str, Any]:
    """Lease rows as they are. Nothing here expires or releases one."""
    same_org(org_id, ctx)
    rows = (
        db.connection()
        .execute(
            sa.select(
                LEASES.c.job_id,
                LEASES.c.source_id,
                LEASES.c.lease_owner,
                LEASES.c.lease_acquired_at,
                LEASES.c.lease_expires_at,
                LEASES.c.lease_status,
                LEASES.c.failure_class,
                LEASES.c.attempt_count,
                LEASES.c.max_attempts,
                LEASES.c.next_retry_at,
            )
            .where(LEASES.c.organization_id == org_id)
            .limit(200)
        )
        .mappings()
        .all()
    )
    leases = [dict(row) for row in rows]
    return envelope(
        {
            "leases": leases,
            "lease_count": len(leases),
            "held": sum(1 for row in leases if row["lease_owner"]),
            "stale_leases": _stale_lease_count(db, org_id, DEFAULT_EVALUATION_INSTANT),
            "nothing_here_sweeps_a_lease": (
                "a sweeper is a scheduled job, and Gate 159 owns triggers"
            ),
            "collectors_invoked": 0,
            "source_monitoring_live": False,
        }
    )


@router.post("/{org_id}/source-worker/dry-run")
def post_worker_dry_run(
    org_id: uuid.UUID,
    ctx: Annotated[OrgContext, Depends(require_demo_org_session)],
    body: Annotated[dict[str, Any] | None, Body()] = None,
) -> dict[str, Any]:
    """Evaluate a worker cycle in memory. Claims nothing, writes nothing."""
    same_org(org_id, ctx)
    payload = body or {}
    now = str(payload.get("now") or DEFAULT_EVALUATION_INSTANT)
    cycle = _in_memory_cycle(now, org_id)
    failures = worker_cycle_invariant_failures(cycle)
    if failures:
        raise HTTPException(status_code=500, detail="worker_cycle_refused")

    return envelope(
        {
            "ran": cycle["ran"],
            "why_not": cycle["blocked_reasons"],
            "no_connection_is_supplied_on_purpose": (
                "claiming a lease from a request would take a claim a real "
                "worker then could not have, released only by expiry"
            ),
            "jobs_that_would_be_offered": len(_scheduler_jobs(now)),
            "jobs_claimed": cycle["jobs_claimed"],
            "jobs_completed": cycle["jobs_completed"],
            # Constants. A dry run evaluates.
            "collectors_invoked": 0,
            "live_source_calls": 0,
            "network_calls": 0,
            "rows_written": 0,
            "leases_taken": 0,
            "activation_changed": False,
            "source_approved": False,
            "source_monitoring_live": False,
        }
    )
