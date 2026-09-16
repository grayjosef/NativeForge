"""Orchestration routes (Gate 159J).

Three reads and one dry-run POST, all under the demo prefix and all behind
`require_demo_org_session`.

## The POST evaluates; it does not orchestrate

`/orchestration/dry-run` runs a full cycle inside a SAVEPOINT and rolls it back,
reporting what *would* have happened and the row counts on both sides so the
claim that nothing persisted is a measurement rather than a promise.

That matters more here than it did for Gate 158's job store, because a cycle
takes OWNERSHIP of a slot. A dry run that committed would consume the real
slot, and the next genuine wake would be told `already_triggered` - a read
endpoint would have silently suppressed a real cycle.

## Three conditions this cannot honestly report

`expired_owner_reclaimable`, `missed_window_recovered` and
`restart_is_idempotent` each need a process to die, time to pass, or a second
process to exist. A request has none of those. The health route therefore
supplies no evidence for them, reports the lane red, and names the verifier -
the same shape Gate 158 settled on after its health route claimed a restart
proof it could not produce.

`NOT_MEASURABLE_BY_A_REQUEST` is imported rather than restated, so the route
and the health service cannot drift apart about which three they are.
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
from nativeforge.repositories.source_collection_job_repository import count_backlog
from nativeforge.repositories.source_collection_orchestration_lock_repository import (
    CYCLES,
    count_cycles,
    list_stale_owners,
    orchestration_lock_invariant_failures,
    read_last_served_slot,
)
from nativeforge.services.source_collection_orchestration_health_service import (
    NOT_MEASURABLE_BY_A_REQUEST,
    build_orchestration_health,
    orchestration_health_invariant_failures,
)
from nativeforge.services.source_collection_orchestration_identity_service import (
    DEFAULT_CADENCE,
    build_orchestration_identity,
    orchestration_identity_invariant_failures,
)
from nativeforge.services.source_collection_orchestration_runtime_service import (
    COMPOSES,
    orchestration_cycle_invariant_failures,
    run_orchestration_cycle,
)
from nativeforge.services.source_collection_periodic_trigger_service import (
    DEFAULT_MAX_CATCHUP_SLOTS,
    build_trigger_schedule,
    evaluate_trigger,
    trigger_invariant_failures,
)
from nativeforge.services.source_monitoring_approved_source_service import (
    load_registry_rows,
)

router = APIRouter(prefix="/v1/nf/demo/orgs", tags=["source-orchestration-demo"])

#: Fixed so a response is reproducible and a test does not race the clock.
DEFAULT_EVALUATION_INSTANT = "2026-09-15T12:00:00Z"

#: A bounded slice of the registry. A dry run that inserts and rolls back 177
#: rows to answer one request is a route nobody will leave enabled.
DEFAULT_DRY_RUN_LIMIT = 25


def _registry_sources(limit: int) -> list[dict[str, Any]]:
    """Registry keys as scheduler input, every prerequisite unsatisfied."""
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
        for key in sorted(load_registry_rows())[: int(limit)]
    ]


def _cycle_row_count(db: Session, org_id: uuid.UUID) -> int:
    try:
        return int(
            db.connection()
            .execute(
                sa.select(sa.func.count())
                .select_from(CYCLES)
                .where(CYCLES.c.organization_id == org_id)
            )
            .scalar()
            or 0
        )
    except Exception:  # noqa: BLE001 - a health read that 500s is worse
        return 0


@router.get("/{org_id}/orchestration/health")
def get_orchestration_health(
    org_id: uuid.UUID,
    ctx: Annotated[OrgContext, Depends(require_demo_org_session)],
    db: Annotated[Session, Depends(get_db_session)],
    now: str | None = None,
) -> dict[str, Any]:
    # Raises 404 itself, and 404 rather than 403 on purpose: a 403 confirms the
    # organization exists to somebody who is not in it.
    same_org(org_id, ctx)

    instant = str(now or DEFAULT_EVALUATION_INSTANT)
    connection = db.connection()

    history = read_last_served_slot(
        connection=connection,
        organization_id=str(org_id),
        cadence=DEFAULT_CADENCE,
        now=instant,
    )
    trigger = evaluate_trigger(
        now=instant,
        last_served_slot_index=history.get("last_served_slot_index"),
        cadence=DEFAULT_CADENCE,
    )
    counts = count_cycles(connection=connection, organization_id=str(org_id))
    backlog = count_backlog(connection=connection, organization_id=str(org_id))
    stale = list_stale_owners(
        connection=connection, organization_id=str(org_id), now=instant
    )

    # Determinism IS measurable from a request: it is arithmetic, not a
    # process. Recomputed here rather than asserted.
    first = build_orchestration_identity(now=instant, cadence=DEFAULT_CADENCE)
    second = build_orchestration_identity(now=instant, cadence=DEFAULT_CADENCE)
    deterministic = (
        first["cycle_id"] == second["cycle_id"]
        and not orchestration_identity_invariant_failures(first)
    )

    # And so are these three, inside a SAVEPOINT that is rolled back. Running
    # a cycle for real would consume the slot, and the next genuine wake would
    # be told `already_triggered` - a READ endpoint would have suppressed a
    # real cycle. The savepoint is what makes measuring them safe.
    savepoint = connection.begin_nested()
    try:
        probed = run_orchestration_cycle(
            connection=connection,
            organization_id=str(org_id),
            owner_id=f"nf-health-probe-{uuid.uuid4().hex[:8]}",
            sources=_registry_sources(DEFAULT_DRY_RUN_LIMIT),
            now=instant,
            cadence=DEFAULT_CADENCE,
        )
        # A SECOND attempt at the same slot, by a DIFFERENT owner. It must be
        # refused, and it must do no work.
        duplicate = run_orchestration_cycle(
            connection=connection,
            organization_id=str(org_id),
            owner_id=f"nf-health-probe-second-{uuid.uuid4().hex[:8]}",
            sources=_registry_sources(DEFAULT_DRY_RUN_LIMIT),
            now=instant,
            cadence=DEFAULT_CADENCE,
        )
    finally:
        savepoint.rollback()

    probe_rows_left = _cycle_row_count(db, org_id)

    health = build_orchestration_health(
        cycle=probed,
        trigger=trigger,
        identity_is_deterministic=deterministic,
        duplicate_trigger_result=duplicate,
        # The second attempt was a different owner in the same slot, so its
        # refusal is the single-active-owner proof as well as the duplicate
        # one. Both halves: refused, AND it created nothing.
        concurrent_owner_refused=(
            not duplicate["ran"] and int(duplicate["jobs_created"] or 0) == 0
        ),
        cycle_counts=counts,
        backlog=backlog,
        stale_cycle_owners=stale["stale_owner_count"],
        # Not supplied on purpose. A request cannot kill a process, wait for a
        # lease to lapse, or be two processes across a restart.
        expired_owner_reclaimed=None,
        missed_window_result=None,
        restart_recovered_nothing=None,
        # Nor can it see the host's process table.
        orchestration_process_active=None,
    )

    return envelope(
        {
            **health,
            "organization_id": str(org_id),
            "evaluated_at": instant,
            "invariant_failures": orchestration_health_invariant_failures(health),
            "trigger_invariant_failures": trigger_invariant_failures(trigger),
            "lock_invariant_failures": orchestration_lock_invariant_failures(counts),
            "measured_by_the_verifier": list(NOT_MEASURABLE_BY_A_REQUEST),
            # Every red condition should be one a request genuinely cannot
            # measure. If these two lists ever disagree, something is red for
            # a reason nobody has explained.
            "every_unmet_condition_is_explained": sorted(
                health["conditions_not_met"]
            )
            == sorted(NOT_MEASURABLE_BY_A_REQUEST),
            "health_probe_rolled_back": True,
            # Measured after the rollback. A promise that the slot was not
            # consumed is worth less than a count of what is there.
            "health_probe_cycle_rows_left_behind": probe_rows_left,
            "why": (
                "reclaiming an expired owner needs a process to die and a "
                "lease to lapse; recovering a missed window needs downtime; "
                "restart idempotency needs a second process. A request has "
                "none of those, so "
                "scripts/verify_nativeforge_source_orchestration_runtime.sh "
                "measures them and this lane stays red here."
            ),
            "composes": list(COMPOSES),
        }
    )


@router.get("/{org_id}/orchestration/trigger")
def get_orchestration_trigger(
    org_id: uuid.UUID,
    ctx: Annotated[OrgContext, Depends(require_demo_org_session)],
    db: Annotated[Session, Depends(get_db_session)],
    now: str | None = None,
    cadence: str = DEFAULT_CADENCE,
) -> dict[str, Any]:
    same_org(org_id, ctx)

    instant = str(now or DEFAULT_EVALUATION_INSTANT)
    history = read_last_served_slot(
        connection=db.connection(),
        organization_id=str(org_id),
        cadence=cadence,
        now=instant,
    )
    trigger = evaluate_trigger(
        now=instant,
        last_served_slot_index=history.get("last_served_slot_index"),
        cadence=cadence,
        max_catchup_slots=DEFAULT_MAX_CATCHUP_SLOTS,
    )
    return envelope(
        {
            **trigger,
            "organization_id": str(org_id),
            "last_served_slot_index": history.get("last_served_slot_index"),
            "unfinished_slots": history.get("unfinished_slot_count"),
            "served_definition": history.get("served_definition"),
            "upcoming_wakes": build_trigger_schedule(now=instant, cadence=cadence)[
                "wakes"
            ],
            "invariant_failures": trigger_invariant_failures(trigger),
            "a_trigger_is_not_a_source_check": True,
        }
    )


@router.get("/{org_id}/orchestration/missed-windows")
def get_missed_windows(
    org_id: uuid.UUID,
    ctx: Annotated[OrgContext, Depends(require_demo_org_session)],
    db: Annotated[Session, Depends(get_db_session)],
    now: str | None = None,
) -> dict[str, Any]:
    same_org(org_id, ctx)

    instant = str(now or DEFAULT_EVALUATION_INSTANT)
    connection = db.connection()
    history = read_last_served_slot(
        connection=connection,
        organization_id=str(org_id),
        cadence=DEFAULT_CADENCE,
        now=instant,
    )
    trigger = evaluate_trigger(
        now=instant,
        last_served_slot_index=history.get("last_served_slot_index"),
        cadence=DEFAULT_CADENCE,
    )
    stale = list_stale_owners(
        connection=connection, organization_id=str(org_id), now=instant
    )

    return envelope(
        {
            "organization_id": str(org_id),
            "evaluated_at": instant,
            "cadence": DEFAULT_CADENCE,
            "state": trigger["state"],
            "last_served_slot_index": history.get("last_served_slot_index"),
            # A slot whose owner died. Reported so a later reclaim is
            # explicable rather than looking like a slot that ran twice.
            "unfinished_slots": history.get("unfinished_slot_count"),
            "missed_slot_indexes": trigger["missed_slot_indexes"],
            "missed_slot_count": trigger["missed_slot_count"],
            "recoverable_slot_indexes": trigger["recoverable_slot_indexes"],
            "recoverable_slot_count": trigger["recoverable_slot_count"],
            "max_catchup_slots": trigger["max_catchup_slots"],
            "slots_dropped_by_the_bound": trigger["slots_dropped_by_the_bound"],
            "catchup_was_bounded": trigger["catchup_was_bounded"],
            "oldest_recoverable_slot_key": trigger["oldest_recoverable_slot_key"],
            "stale_cycle_owners": stale["stale_owner_count"],
            "invariant_failures": trigger_invariant_failures(trigger),
            "recovery_does_not_invent_work": (
                "source schedules do not advance until a check happens, so "
                "every recovered slot computes the same Gate 158 job ids and "
                "deduplicates. Recovery records that a slot was served."
            ),
            "source_monitoring_live": False,
        }
    )


@router.post("/{org_id}/orchestration/dry-run")
def post_orchestration_dry_run(
    org_id: uuid.UUID,
    ctx: Annotated[OrgContext, Depends(require_demo_org_session)],
    db: Annotated[Session, Depends(get_db_session)],
    payload: Annotated[dict[str, Any] | None, Body()] = None,
) -> dict[str, Any]:
    """What would one orchestration cycle do? Run it, measure, roll back."""
    same_org(org_id, ctx)

    body = payload or {}
    instant = str(body.get("now") or DEFAULT_EVALUATION_INSTANT)
    limit = int(body.get("limit") or DEFAULT_DRY_RUN_LIMIT)

    connection = db.connection()
    cycles_before = _cycle_row_count(db, org_id)

    savepoint = connection.begin_nested()
    try:
        report = run_orchestration_cycle(
            connection=connection,
            organization_id=str(org_id),
            owner_id=f"nf-route-dry-run-{uuid.uuid4().hex[:8]}",
            sources=_registry_sources(limit),
            now=instant,
            cadence=DEFAULT_CADENCE,
        )
        cycles_inside = _cycle_row_count(db, org_id)
    finally:
        savepoint.rollback()

    cycles_after = _cycle_row_count(db, org_id)

    return envelope(
        {
            **report,
            "organization_id": str(org_id),
            "evaluated_at": instant,
            "sources_offered": limit,
            # The measurement that makes "nothing persisted" checkable, and
            # that matters more here than for a job store: a committed dry run
            # would consume the real slot and silently suppress the next
            # genuine cycle.
            "cycle_rows_before": cycles_before,
            "cycle_rows_inside_the_savepoint": cycles_inside,
            "cycle_rows_after": cycles_after,
            "rolled_back": True,
            "nothing_persisted": cycles_after == cycles_before,
            # And the proof it was not a no-op. A dry run that could not write
            # proves nothing about what a real cycle would do.
            "the_savepoint_actually_held_rows": cycles_inside > cycles_before,
            "invariant_failures": orchestration_cycle_invariant_failures(report),
            "the_slot_was_not_consumed": (
                "the ownership row was rolled back, so the next real wake "
                "still finds this slot unserved"
            ),
        }
    )
