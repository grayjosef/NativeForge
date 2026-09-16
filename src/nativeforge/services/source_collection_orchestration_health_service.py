"""Orchestration health (Gate 159I).

## The lane, and the two things it must say at once

```text
orchestration_runtime_ready = True    the loop wakes, exactly once per slot,
                                      and recovers what it missed
jobs_completed              = 0       and nothing has been collected
source_monitoring_live      = False
```

A periodic trigger is the single most plausible thing in this campaign to
mistake for live monitoring. Something now wakes on a cadence and writes rows;
that is precisely the shape of a system that is watching sources. It is not
watching anything, and this lane has to keep both halves sayable.

## `orchestration_process_active` is measured, not declared

Whether a process is running is a fact about the host, not about this code, so
it is supplied by whoever can see the host - the verifier reads systemd, the
route reports the absence honestly. A service that reported itself active
because its own module had imported would be measuring the wrong thing.

Gate 154 shipped a lane that weighed only the conditions it expected to matter
and then named a real failure in `blockers` and ignored it. Here `ready` is
`all(conditions) and not blockers`, so anything in `blockers` closes the lane.

## What ready does not mean

The orchestrator wakes the scheduler. It does not make the scheduler able to do
anything it could not do before: the same sources are blocked for the same
reasons, no collector exists, and 171 sources still wait on a human reading
their terms.
"""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services.source_collection_orchestration_runtime_service import (
    orchestration_cycle_invariant_failures,
)
from nativeforge.services.source_collection_periodic_trigger_service import (
    TRIGGER_STATES,
    trigger_invariant_failures,
)

SCHEMA_VERSION = "nf_source_collection_orchestration_health_v1"

CONTROLLED_SCOPE = "controlled_dev_demo"

CONDITIONS: tuple[str, ...] = (
    "cycle_completed",
    "cycle_identity_is_deterministic",
    "duplicate_trigger_suppressed",
    "single_active_owner",
    "expired_owner_reclaimable",
    "missed_window_recovered",
    "catchup_is_bounded",
    "restart_is_idempotent",
    "nothing_collected",
)

CONDITION_EVIDENCE: dict[str, str] = {
    "cycle_completed": (
        "an orchestration cycle ran end to end and its own invariants were "
        "clean"
    ),
    "cycle_identity_is_deterministic": (
        "the same trigger slot produced the same cycle id, and a different "
        "slot a different one, recomputed rather than asserted"
    ),
    "duplicate_trigger_suppressed": (
        "a second trigger attempt inside one slot did no work and was refused "
        "by name, rather than silently doing the work twice"
    ),
    "single_active_owner": (
        "a second process could not own a slot whose owner had not expired, "
        "refused by a unique index rather than by a check with a race window "
        "in front of it"
    ),
    "expired_owner_reclaimable": (
        "a slot whose owner lapsed without releasing was taken by another "
        "process, so one crashed orchestrator does not block its slot "
        "forever. Gate 159 measured this path unreachable at first: the "
        "history read counted a crashed slot as served, so the trigger "
        "refused before acquisition was ever attempted."
    ),
    "missed_window_recovered": (
        "a trigger slot that went unserved during downtime was served once "
        "on the next wake"
    ),
    "catchup_is_bounded": (
        "the trigger's recoverable set never exceeded max_catchup_slots, and "
        "catchup_was_bounded agrees with whether any slots were dropped. "
        "Measured against the bound rather than by comparing a count with "
        "itself, which is what the first version of this condition did."
    ),
    "restart_is_idempotent": (
        "running the same instant again recovered nothing new and wrote no "
        "cycle row"
    ),
    "nothing_collected": (
        "zero completed jobs and zero execution proofs, counted from the job "
        "store, and zero rows in the cycle table claiming a collector or a "
        "live call - values the database refuses to let grow"
    ),
}

#: Conditions a single HTTP request cannot honestly measure. Exported so the
#: route names this list rather than keeping its own copy, which is how the two
#: would come to disagree. Gate 158 learned this when its health route claimed
#: a restart proof it could not produce.
NOT_MEASURABLE_BY_A_REQUEST: tuple[str, ...] = (
    "expired_owner_reclaimable",
    "missed_window_recovered",
    "restart_is_idempotent",
)

READY_DOES_NOT_MEAN: tuple[str, ...] = (
    "a source was contacted",
    "a collector ran",
    "a source is approved",
    "source terms were accepted",
    "a schedule advanced",
    "monitoring is live",
    "a job was completed",
)


def _json_safe(value: Any) -> Any:
    return json.loads(json.dumps(value, default=str, sort_keys=True))


def build_orchestration_health(
    *,
    cycle: dict[str, Any] | None = None,
    trigger: dict[str, Any] | None = None,
    identity_is_deterministic: Any = None,
    duplicate_trigger_result: dict[str, Any] | None = None,
    concurrent_owner_refused: Any = None,
    expired_owner_reclaimed: Any = None,
    missed_window_result: dict[str, Any] | None = None,
    restart_recovered_nothing: Any = None,
    cycle_counts: dict[str, Any] | None = None,
    backlog: dict[str, Any] | None = None,
    orchestration_process_active: Any = None,
    stale_cycle_owners: Any = None,
) -> dict[str, Any]:
    """Report the lane from results somebody else measured.

    Opens no connection and runs no cycle, so it cannot pass its own lane by
    doing the work it is grading.
    """
    ran = cycle or {}
    decision = trigger or {}
    duplicate = duplicate_trigger_result or {}
    recovery = missed_window_result or {}
    counts = cycle_counts or {}
    jobs = backlog or {}

    blockers: list[str] = []

    # Propagate the invariants of every supplied result. A lane that ignores
    # the invariant failures of its own evidence is grading a summary.
    if ran:
        for failure in orchestration_cycle_invariant_failures(ran):
            blockers.append(f"cycle:{failure}")
    if decision:
        for failure in trigger_invariant_failures(decision):
            blockers.append(f"trigger:{failure}")

    completed = int(jobs.get("completed_total") or 0)
    proofs = int(jobs.get("rows_with_execution_proof") or 0)
    claiming_completion = int(counts.get("rows_claiming_a_completion") or 0)
    claiming_collector = int(counts.get("rows_claiming_a_collector") or 0)
    claiming_live = int(counts.get("rows_claiming_a_live_call") or 0)

    if completed:
        blockers.append(f"the_job_store_holds_a_completed_job:{completed}")
    if proofs:
        blockers.append(f"the_job_store_holds_an_execution_proof:{proofs}")
    if claiming_completion:
        blockers.append(f"a_cycle_row_claims_a_completion:{claiming_completion}")
    if claiming_collector:
        blockers.append(f"a_cycle_row_claims_a_collector:{claiming_collector}")
    if claiming_live:
        blockers.append(f"a_cycle_row_claims_a_live_call:{claiming_live}")

    stale = int(stale_cycle_owners or 0)

    measured = {
        "cycle_completed": bool(ran.get("ran"))
        and not orchestration_cycle_invariant_failures(ran),
        "cycle_identity_is_deterministic": bool(identity_is_deterministic),
        # Both halves: refused AND did no work. "Suppressed" would also be true
        # of an attempt that quietly ran the cycle and reported a refusal.
        "duplicate_trigger_suppressed": bool(
            duplicate
            and not duplicate.get("ran")
            and int(duplicate.get("duplicate_triggers_suppressed") or 0) > 0
            and int(duplicate.get("jobs_created") or 0) == 0
        ),
        "single_active_owner": bool(concurrent_owner_refused),
        "expired_owner_reclaimable": bool(expired_owner_reclaimed),
        "missed_window_recovered": bool(
            recovery and int(recovery.get("slots_recovered") or 0) > 0
        ),
        # Measured against the trigger's own bound, and only from a decision
        # that actually carries one. The first version of this compared
        # `slots_offered` with itself, which is true of every input.
        "catchup_is_bounded": bool(
            decision
            and decision.get("max_catchup_slots")
            and int(decision.get("recoverable_slot_count") or 0)
            <= int(decision.get("max_catchup_slots") or 0)
            # And when the bound bit, the dropped slots are reported rather
            # than discarded: a system that silently threw away a week of
            # slots would otherwise pass this condition.
            and bool(decision.get("catchup_was_bounded"))
            is (int(decision.get("slots_dropped_by_the_bound") or 0) > 0)
        ),
        "restart_is_idempotent": bool(restart_recovered_nothing),
        "nothing_collected": bool(jobs)
        and completed == 0
        and proofs == 0
        and claiming_completion == 0
        and claiming_collector == 0
        and claiming_live == 0,
    }

    missing = sorted(name for name, ok in measured.items() if not ok)
    blockers.extend(f"condition_not_met:{name}" for name in missing)

    ready = all(measured.values()) and not blockers

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "scope": CONTROLLED_SCOPE,
            "orchestration_runtime_ready": ready,
            "conditions": measured,
            "conditions_expected": list(CONDITIONS),
            "condition_evidence": CONDITION_EVIDENCE,
            "conditions_not_met": missing,
            "blockers": sorted(set(blockers)),
            "blocker_count": len(set(blockers)),
            "not_measurable_by_a_request": list(NOT_MEASURABLE_BY_A_REQUEST),
            # ---- the process, measured by whoever can see the host -------
            "orchestration_process_active": bool(orchestration_process_active),
            "process_state_is_supplied_not_detected": (
                "whether a process is running is a fact about the host. A "
                "service reporting itself active because its own module "
                "imported would be measuring the wrong thing."
            ),
            # ---- the last cycle ------------------------------------------
            "last_cycle_id": ran.get("orchestration_cycle_id"),
            "last_cycle_started_at": ran.get("started_at"),
            "last_cycle_completed_at": ran.get("completed_at"),
            "last_cycle_owner": ran.get("owner_id"),
            "last_cycle_slot_index": ran.get("slot_index"),
            "last_cycle_slot_key": ran.get("slot_key"),
            "cadence": ran.get("cadence") or decision.get("cadence"),
            # ---- the trigger ---------------------------------------------
            "trigger_state": decision.get("state") or ran.get("trigger_state"),
            "trigger_states": list(TRIGGER_STATES),
            "next_trigger_at": decision.get("next_wake_at")
            or ran.get("next_trigger_at"),
            "duplicate_triggers_suppressed": int(
                ran.get("duplicate_triggers_suppressed") or 0
            )
            + int(duplicate.get("duplicate_triggers_suppressed") or 0),
            "missed_windows_detected": int(ran.get("missed_windows_detected") or 0),
            "missed_windows_recovered": int(recovery.get("slots_recovered") or 0)
            or int(ran.get("missed_windows_recovered") or 0),
            "slots_dropped_by_the_bound": int(
                recovery.get("slots_dropped_by_the_bound")
                or ran.get("slots_dropped_by_the_bound")
                or 0
            ),
            "max_catchup_slots": decision.get("max_catchup_slots"),
            # ---- ownership ------------------------------------------------
            "active_cycle_owner": (
                ran.get("owner_id") if ran.get("ran") else None
            ),
            "stale_cycle_owners": stale,
            "cycles_by_status": counts.get("by_status") or {},
            "cycles_total": int(counts.get("total") or 0),
            "total_reclaims": int(counts.get("total_reclaims") or 0),
            "unfinished_slots": int(ran.get("unfinished_slots") or 0),
            # ---- what the loop produced ----------------------------------
            "sources_seen": int(ran.get("sources_seen") or 0),
            "jobs_created": int(ran.get("jobs_created") or 0),
            "jobs_reused": int(ran.get("jobs_reused") or 0),
            "jobs_blocked": int(ran.get("jobs_blocked") or 0),
            "jobs_claimed": int(ran.get("jobs_claimed") or 0),
            "jobs_refused": int(ran.get("jobs_refused") or 0),
            "jobs_by_status": jobs.get("by_status") or {},
            # ---- the boundary ---------------------------------------------
            "ready_does_not_mean": list(READY_DOES_NOT_MEAN),
            "jobs_completed": completed,
            "rows_with_execution_proof": proofs,
            "cycle_rows_claiming_a_completion": claiming_completion,
            "cycle_rows_claiming_a_collector": claiming_collector,
            "cycle_rows_claiming_a_live_call": claiming_live,
            "collectors_invoked": 0,
            "live_source_calls": 0,
            "network_calls": 0,
            "emails_sent": 0,
            "object_store_calls": 0,
            "approved_source_count": 0,
            "last_checked_at_advanced": False,
            "source_monitoring_live": False,
        }
    )


def orchestration_health_invariant_failures(health: dict[str, Any]) -> list[str]:
    """Refuse a health report that claims monitoring, or contradicts itself."""
    fails: list[str] = []

    for counter in (
        "collectors_invoked",
        "live_source_calls",
        "network_calls",
        "emails_sent",
        "object_store_calls",
        "approved_source_count",
        "jobs_completed",
        "rows_with_execution_proof",
        "cycle_rows_claiming_a_completion",
        "cycle_rows_claiming_a_collector",
        "cycle_rows_claiming_a_live_call",
    ):
        if int(health.get(counter) or 0) != 0:
            fails.append(f"health_counted:{counter}={health.get(counter)}")

    if health.get("source_monitoring_live"):
        fails.append("health_claimed:source_monitoring_live")
    if health.get("last_checked_at_advanced"):
        fails.append("health_claimed:last_checked_at_advanced")

    # The Gate 154 defect, both directions.
    if health.get("orchestration_runtime_ready") and health.get("blockers"):
        fails.append("ready_alongside_blockers")
    if health.get("orchestration_runtime_ready") and health.get(
        "conditions_not_met"
    ):
        fails.append("ready_alongside_unmet_conditions")
    if not health.get("orchestration_runtime_ready") and not health.get("blockers"):
        fails.append("not_ready_without_naming_a_blocker")

    conditions = health.get("conditions") or {}
    expected = set(health.get("conditions_expected") or ())
    if expected and set(conditions) != expected:
        fails.append("conditions_do_not_match_the_declared_set")

    evidence = health.get("condition_evidence") or {}
    for name in conditions:
        if not str(evidence.get(name) or "").strip():
            fails.append(f"condition_without_evidence:{name}")

    # A ready lane that reports live monitoring, or omits the disclaimer, is
    # the exact confusion this lane exists to prevent.
    if health.get("orchestration_runtime_ready"):
        if not health.get("ready_does_not_mean"):
            fails.append("ready_without_stating_what_ready_does_not_mean")
        if conditions.get("nothing_collected") is not True:
            fails.append("ready_while_something_was_collected")

    state = health.get("trigger_state")
    if state is not None and state not in (health.get("trigger_states") or ()):
        fails.append(f"trigger_state_outside_vocabulary:{state}")

    # Recovery cannot exceed detection.
    if int(health.get("missed_windows_recovered") or 0) > int(
        health.get("missed_windows_detected") or 0
    ):
        fails.append("recovered_more_windows_than_were_detected")

    # An active owner is only meaningful for a cycle that ran.
    if health.get("active_cycle_owner") and not conditions.get("cycle_completed"):
        fails.append("an_active_owner_without_a_completed_cycle")

    by_status = health.get("cycles_by_status") or {}
    if by_status and sum(by_status.values()) != int(health.get("cycles_total") or 0):
        fails.append("cycles_by_status_does_not_account_for_the_total")

    return sorted(set(fails))
