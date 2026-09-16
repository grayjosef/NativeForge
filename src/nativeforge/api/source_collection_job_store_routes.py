"""Job store routes (Gate 158H).

Four reads and one dry-run POST, all under the demo prefix and all behind
`require_demo_org_session`.

## The POST writes nothing

`/job-store/dry-run` enqueues into a SAVEPOINT and rolls it back. It reports
what *would* have been written - how many rows are new, how many the unique
index would refuse - and the row count before and after, measured, so the claim
that nothing persisted is a measurement rather than a promise.

Gate 157's equivalent route passed no connection at all, which made the refusal
unfalsifiable: it proved a route cannot take a lease, but it could not show what
enqueueing would do. This one does the work and then undoes it, and reports the
before/after counts that prove the undo happened.

## Why a rollback rather than no connection

A dry run that cannot reach the database can only ever say "no". The useful
question an operator has is *what would a cycle write* - and answering it needs
a real insert against the real unique index. The safety comes from the
SAVEPOINT, and it is checked by comparing the table count on both sides.
"""

from __future__ import annotations

import uuid
from typing import Annotated, Any

import sqlalchemy as sa
from fastapi import APIRouter, Body, Depends
from sqlalchemy.orm import Session

from nativeforge.api.customer_org_context_dependency import require_demo_org_session
from nativeforge.api.deps_db import get_db_session
from nativeforge.api.org_context import OrgContext
from nativeforge.api.post_award_common import envelope, same_org
from nativeforge.repositories.source_collection_job_repository import (
    JOBS,
    QUEUED,
    count_backlog,
    job_store_capability,
    job_store_invariant_failures,
    list_jobs,
    transition_job,
)
from nativeforge.services.source_collection_job_identity_service import (
    build_job_identity,
    identity_invariant_failures,
)
from nativeforge.services.source_collection_job_store_health_service import (
    NOT_MEASURABLE_BY_A_REQUEST,
    build_job_store_health,
    job_store_health_invariant_failures,
)
from nativeforge.services.source_collection_scheduler_loop_service import (
    CYCLE_MODE_EVALUATE_AND_ENQUEUE,
    cycle_invariant_failures,
    run_scheduler_cycle,
)
from nativeforge.services.source_monitoring_approved_source_service import (
    load_registry_rows,
)

router = APIRouter(prefix="/v1/nf/demo/orgs", tags=["source-job-store-demo"])

#: Fixed so a response is reproducible and a test does not race the clock.
DEFAULT_EVALUATION_INSTANT = "2026-09-15T12:00:00Z"

#: A bounded slice of the registry. The whole registry is 177 rows, and a route
#: that inserts and rolls back 177 rows to answer a GET is a route nobody will
#: leave enabled.
DEFAULT_DRY_RUN_LIMIT = 25


def _registry_sources(limit: int) -> list[dict[str, Any]]:
    """Registry keys as scheduler input. Every prerequisite unsatisfied.

    None of these values is a guess about a source - they are the measured
    state of an empty allowlist, spelled out so the scheduler refuses each one
    for a named reason rather than for a missing key.
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
        }
        for key in sorted(rows)[: int(limit)]
    ]


def _table_count(db: Session, org_id: uuid.UUID) -> int:
    try:
        return int(
            db.connection()
            .execute(
                sa.select(sa.func.count())
                .select_from(JOBS)
                .where(JOBS.c.organization_id == org_id)
            )
            .scalar()
            or 0
        )
    except Exception:  # noqa: BLE001 - a health read that 500s is worse
        return 0


def _table_exists(db: Session) -> bool:
    try:
        db.connection().execute(sa.select(sa.func.count()).select_from(JOBS)).scalar()
    except Exception:  # noqa: BLE001
        return False
    return True


@router.get("/{org_id}/job-store/health")
def get_job_store_health(
    org_id: uuid.UUID,
    ctx: Annotated[OrgContext, Depends(require_demo_org_session)],
    db: Annotated[Session, Depends(get_db_session)],
) -> dict[str, Any]:
    # Raises 404 itself, and 404 rather than 403 on purpose: a 403 confirms
    # the organization exists to somebody who is not in it.
    same_org(org_id, ctx)

    connection = db.connection()
    backlog = count_backlog(connection=connection, organization_id=str(org_id))

    # The lane's evidence is produced inside a SAVEPOINT and rolled back, so a
    # health read does not leave a fixture row behind. The store this reports
    # on is the same store, measured, not a copy.
    probe_id = f"nf-health-158-{uuid.uuid4().hex[:12]}"
    identity = build_job_identity(source_id=probe_id, scheduled_for=None)
    savepoint = connection.begin_nested()
    try:
        from nativeforge.repositories.source_collection_job_repository import (
            enqueue_job,
        )

        first = enqueue_job(
            connection=connection,
            organization_id=str(org_id),
            job_id=identity["job_id"],
            idempotency_key=identity["idempotency_key"],
            source_id=probe_id,
            schedule_key=identity["schedule_key"],
            created_by_runtime="verifier_fixture",
            now=DEFAULT_EVALUATION_INSTANT,
        )
        second = enqueue_job(
            connection=connection,
            organization_id=str(org_id),
            job_id=identity["job_id"],
            idempotency_key=identity["idempotency_key"],
            source_id=probe_id,
            schedule_key=identity["schedule_key"],
            created_by_runtime="verifier_fixture",
            now=DEFAULT_EVALUATION_INSTANT,
        )
        # NOTE what is deliberately not done here. Reading the row back
        # through this same connection would make `survives_restart` go green
        # for the wrong reason: an uncommitted write is visible to the session
        # that made it whether or not the row is durable. So no restart
        # evidence is supplied, and the verifier - which can commit and
        # reconnect - is what measures it.
        #
        # `queued -> refused` is not in the state machine.
        illegal = transition_job(
            connection=connection,
            organization_id=str(org_id),
            job_id=identity["job_id"],
            to_status="refused",
            terminal_reason="terms_blocked",
            now=DEFAULT_EVALUATION_INSTANT,
        )
    finally:
        savepoint.rollback()

    left_behind = list_jobs(
        connection=connection, organization_id=str(org_id), source_id=probe_id
    )

    health = build_job_store_health(
        table_exists=_table_exists(db),
        enqueue_result=first,
        duplicate_enqueue_result=second,
        # Not supplied on purpose. See the comment above.
        reread_after_reconnect=None,
        illegal_transition_result=illegal,
        backlog=backlog,
    )

    return envelope(
        {
            **health,
            "organization_id": str(org_id),
            "invariant_failures": job_store_health_invariant_failures(health),
            "identity_invariant_failures": identity_invariant_failures(identity),
            "health_probe_rolled_back": True,
            # Measured after the rollback. A promise that nothing was left
            # behind is worth less than a count of what is there.
            "health_probe_rows_left_behind": left_behind["job_count"],
            # Which conditions this response could not honestly measure, and
            # what does measure them. Read from the health service so the two
            # cannot drift.
            "measured_by_the_verifier": list(NOT_MEASURABLE_BY_A_REQUEST),
            "why": (
                "proving a row survives a restart needs a commit and a "
                "reconnect. A GET that commits fixture rows into the demo org "
                "would be worse than a GET that defers, so "
                "scripts/verify_nativeforge_collection_job_store.sh measures "
                "it and this lane stays red here."
            ),
        }
    )


@router.get("/{org_id}/job-store/jobs")
def get_job_store_jobs(
    org_id: uuid.UUID,
    ctx: Annotated[OrgContext, Depends(require_demo_org_session)],
    db: Annotated[Session, Depends(get_db_session)],
    status: str | None = None,
    source_id: str | None = None,
) -> dict[str, Any]:
    # Raises 404 itself, and 404 rather than 403 on purpose: a 403 confirms
    # the organization exists to somebody who is not in it.
    same_org(org_id, ctx)

    listed = list_jobs(
        connection=db.connection(),
        organization_id=str(org_id),
        status=status,
        source_id=source_id,
    )
    return envelope(
        {
            **listed,
            "organization_id": str(org_id),
            "invariant_failures": job_store_invariant_failures(listed),
            "persisted_job_means_collection_occurred": False,
        }
    )


@router.get("/{org_id}/job-store/backlog")
def get_job_store_backlog(
    org_id: uuid.UUID,
    ctx: Annotated[OrgContext, Depends(require_demo_org_session)],
    db: Annotated[Session, Depends(get_db_session)],
) -> dict[str, Any]:
    # Raises 404 itself, and 404 rather than 403 on purpose: a 403 confirms
    # the organization exists to somebody who is not in it.
    same_org(org_id, ctx)

    backlog = count_backlog(connection=db.connection(), organization_id=str(org_id))
    return envelope(
        {
            **backlog,
            "organization_id": str(org_id),
            "invariant_failures": job_store_invariant_failures(backlog),
            # The number this endpoint exists to make askable: how long has
            # blocked work been waiting.
            "oldest_live_job_queued_at": backlog["oldest_queued_at"],
        }
    )


@router.get("/{org_id}/job-store/capability")
def get_job_store_capability(
    org_id: uuid.UUID,
    ctx: Annotated[OrgContext, Depends(require_demo_org_session)],
) -> dict[str, Any]:
    # Raises 404 itself, and 404 rather than 403 on purpose: a 403 confirms
    # the organization exists to somebody who is not in it.
    same_org(org_id, ctx)

    return envelope(
        {**job_store_capability(), "organization_id": str(org_id)}
    )


@router.post("/{org_id}/job-store/dry-run")
def post_job_store_dry_run(
    org_id: uuid.UUID,
    ctx: Annotated[OrgContext, Depends(require_demo_org_session)],
    db: Annotated[Session, Depends(get_db_session)],
    payload: Annotated[dict[str, Any] | None, Body()] = None,
) -> dict[str, Any]:
    """What would a scheduler cycle write? Enqueue, measure, roll back."""
    # Raises 404 itself, and 404 rather than 403 on purpose: a 403 confirms
    # the organization exists to somebody who is not in it.
    same_org(org_id, ctx)

    body = payload or {}
    now = str(body.get("now") or DEFAULT_EVALUATION_INSTANT)
    limit = int(body.get("limit") or DEFAULT_DRY_RUN_LIMIT)

    connection = db.connection()
    before = _table_count(db, org_id)

    savepoint = connection.begin_nested()
    try:
        cycle = run_scheduler_cycle(
            now=now,
            sources=_registry_sources(limit),
            organization_id=str(org_id),
            mode=CYCLE_MODE_EVALUATE_AND_ENQUEUE,
            connection=connection,
        )
        inside = _table_count(db, org_id)
    finally:
        savepoint.rollback()

    after = _table_count(db, org_id)

    return envelope(
        {
            "organization_id": str(org_id),
            "evaluated_at": now,
            "sources_evaluated": cycle["jobs_known"],
            "would_create": cycle["jobs_enqueued"],
            "would_deduplicate": cycle["jobs_deduplicated"],
            "refusal_reasons": cycle["refusal_reasons"],
            "jobs_executable": cycle["jobs_executable"],
            # The measurement that makes "nothing persisted" checkable.
            "rows_before": before,
            "rows_inside_the_savepoint": inside,
            "rows_after": after,
            "rolled_back": True,
            "nothing_persisted": after == before,
            # And the proof that the dry run was not a no-op: it wrote
            # something before undoing it. A dry run that could not write
            # proves nothing about what a real cycle would do.
            "the_savepoint_actually_held_rows": inside > before,
            "invariant_failures": cycle_invariant_failures(cycle),
            "collectors_invoked": cycle["collectors_invoked"],
            "live_source_calls": cycle["live_source_calls"],
            "network_calls": cycle["network_calls"],
            "urls_fetched": cycle["urls_fetched"],
            "raw_payloads_written": cycle["raw_payloads_written"],
            "approved_source_count": 0,
            "source_monitoring_live": False,
            "queued_status_name": QUEUED,
        }
    )
