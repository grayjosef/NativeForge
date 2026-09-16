"""Missed-window recovery (Gate 159F).

## What a missed window is here, and what it is not

Doc 827 measured why this matters:

```text
nf_opportunity_sources rows            40
newest last_checked_at        2026-06-29 21:44:29
nf_source_check_runs rows               0
```

`last_checked_at` is eleven weeks stale and nothing advances it, because
advancing it is what an actual source check does and none has happened. So
every source sits permanently due in a slot that never moves.

A missed window is therefore **an orchestration trigger slot that went
unserved**, not a source check that came due and was skipped. Those are
different clocks, and conflating them would make recovery walk a source cadence
that has not advanced since June.

## Recovering a slot does not invent work

Because the source slot never moves, every recovered orchestration slot
evaluates the *same* source schedules and computes the *same* Gate 158 job ids.
So:

```text
recovering 1 missed slot    creates 1 cycle row,  0 new job rows
recovering 5 missed slots   creates 5 cycle rows, 0 new job rows
```

That is not a defect, and it is the reason recovery is safe. Gate 158's
deterministic `job_id` plus its unique index absorb the repetition: recovery
records *that the slot was served* and re-enqueues the same work, which
deduplicates. It does not fabricate five copies of a backlog.

`jobs_created` on a recovery pass being zero is the honest number, and the
report says so rather than counting reused rows as created ones.

## The bound, and where it lives

The bound is applied by the trigger (`max_catchup_slots`), not chosen here, so a
caller cannot request an unbounded catch-up by calling recovery directly. This
module recovers exactly the slots the trigger declared recoverable and reports
how many the bound dropped.

Without a bound, a process down for a month at hourly cadence would wake and
replay seven hundred slots - each one a full scheduler pass over 177 sources,
all of them producing the same deduplicated rows. Bounded catch-up serves the
most recent slots, because the oldest ones describe work that the newest slot
already covers.

## Restart idempotency

Recovery acquires the cycle row for each slot. Acquisition is atomic on the
unique index, so a second restart finds those rows already present and reports
them suppressed rather than recovering them again.
"""

from __future__ import annotations

import json
from typing import Any

from nativeforge.repositories.source_collection_orchestration_lock_repository import (
    OUTCOME_COMPLETED,
    acquire_cycle,
    orchestration_lock_invariant_failures,
    release_cycle,
)
from nativeforge.services.source_collection_orchestration_identity_service import (
    DEFAULT_CADENCE,
    ORCHESTRATION_VERSION,
    build_cycle_id,
    normalize_cadence,
    slot_started_at,
)

SCHEMA_VERSION = "nf_source_collection_missed_window_v1"

CONTROLLED_SCOPE = "controlled_dev_demo"

RECOVERED = "recovered"
ALREADY_SERVED = "already_served"
REFUSED = "refused"

SLOT_RESULTS: tuple[str, ...] = (RECOVERED, ALREADY_SERVED, REFUSED)


def _json_safe(value: Any) -> Any:
    return json.loads(json.dumps(value, default=str, sort_keys=True))


def recover_missed_windows(
    *,
    connection: Any = None,
    organization_id: Any = None,
    owner_id: Any = None,
    recoverable_slot_indexes: list[int] | None = None,
    cadence: Any = DEFAULT_CADENCE,
    now: Any = None,
    slots_dropped_by_the_bound: int = 0,
    orchestration_version: str | None = None,
    lease_seconds: int | None = None,
    run_cycle: Any = None,
) -> dict[str, Any]:
    """Serve each recoverable slot once, and report which were already served.

    `run_cycle` is an optional callable invoked per recovered slot. It is
    injected rather than imported so this module composes the orchestration
    runtime without importing it - the runtime imports this, and a cycle would
    otherwise be circular.

    When it is None, recovery records the slots and enqueues nothing, which is
    what the identity and bound tests want.
    """
    resolved_cadence = normalize_cadence(cadence)
    slots = [int(index) for index in (recoverable_slot_indexes or [])]
    version = orchestration_version or ORCHESTRATION_VERSION

    blocked: list[str] = []
    if connection is None:
        blocked.append("no_connection_supplied")
    if not str(owner_id or "").strip():
        blocked.append("no_owner_id_supplied")
    if now is None:
        blocked.append("no_clock_supplied")

    per_slot: list[dict[str, Any]] = []
    failures: list[str] = []
    recovered = 0
    already = 0
    refused = 0
    jobs_created = 0
    jobs_reused = 0

    if not blocked:
        # Oldest first, so a partial recovery leaves the newest slots unserved
        # rather than a hole in the middle of the sequence.
        for slot_index in sorted(slots):
            cycle_id = build_cycle_id(
                slot_index=slot_index, cadence=resolved_cadence, version=version
            )
            slot_key = slot_started_at(
                slot_index=slot_index, cadence=resolved_cadence
            ).strftime("%Y-%m-%dT%H:%M:%SZ")

            acquire_kwargs: dict[str, Any] = {
                "connection": connection,
                "organization_id": organization_id,
                "cycle_id": cycle_id,
                "owner_id": owner_id,
                "cadence": resolved_cadence,
                "slot_index": slot_index,
                "slot_key": slot_key,
                "orchestration_version": version,
                "now": now,
                # A recovery pass must not steal a slot another process is
                # actively serving. It is catching up on history, not
                # competing for the present.
                "allow_reclaim": False,
            }
            if lease_seconds is not None:
                acquire_kwargs["lease_seconds"] = int(lease_seconds)

            claim = acquire_cycle(**acquire_kwargs)
            failures.extend(orchestration_lock_invariant_failures(claim))

            if not claim["acquired"]:
                if claim["duplicate_suppressed"]:
                    already += 1
                    outcome = ALREADY_SERVED
                else:
                    refused += 1
                    outcome = REFUSED
                per_slot.append(
                    {
                        "slot_index": slot_index,
                        "slot_key": slot_key,
                        "cycle_id": cycle_id,
                        "result": outcome,
                        "blocked_reasons": claim["blocked_reasons"],
                        "jobs_created": 0,
                        "jobs_reused": 0,
                    }
                )
                continue

            # Owned. Do the work, if a runner was supplied.
            created = 0
            reused = 0
            if callable(run_cycle):
                report = run_cycle(slot_index=slot_index, slot_key=slot_key) or {}
                created = int(report.get("jobs_created") or 0)
                reused = int(report.get("jobs_reused") or 0)

            jobs_created += created
            jobs_reused += reused
            recovered += 1

            done = release_cycle(
                connection=connection,
                organization_id=organization_id,
                cycle_id=cycle_id,
                owner_id=owner_id,
                now=now,
                outcome=OUTCOME_COMPLETED,
                counters={
                    "jobs_created": created,
                    "jobs_reused": reused,
                    "missed_windows_recovered": 1,
                },
            )
            failures.extend(orchestration_lock_invariant_failures(done))

            per_slot.append(
                {
                    "slot_index": slot_index,
                    "slot_key": slot_key,
                    "cycle_id": cycle_id,
                    "result": RECOVERED,
                    "blocked_reasons": [],
                    "jobs_created": created,
                    "jobs_reused": reused,
                }
            )

    dropped = max(0, int(slots_dropped_by_the_bound))

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "scope": CONTROLLED_SCOPE,
            "ran": not blocked,
            "blocked_reasons": sorted(set(blocked)),
            "cadence": resolved_cadence,
            "evaluated_at": None if now is None else str(now),
            "slots_offered": len(slots),
            "slots_recovered": recovered,
            "slots_already_served": already,
            "slots_refused": refused,
            "slots_dropped_by_the_bound": dropped,
            "catchup_was_bounded": dropped > 0,
            "per_slot": per_slot,
            # ---- what recovery actually produced ------------------------
            #
            # Zero created on a repeat is the honest number. Gate 158's
            # deterministic job_id plus its unique index absorb the
            # repetition, and reused rows are NOT counted as created ones.
            "jobs_created": jobs_created,
            "jobs_reused": jobs_reused,
            "a_recovered_slot_may_create_no_work": (
                "source schedules do not advance until a check happens, so "
                "every recovered slot computes the same Gate 158 job ids. "
                "Recovery records that the slot was served; it does not "
                "fabricate copies of a backlog."
            ),
            "invariant_failures": sorted(set(failures)),
            # ---- what recovery is not ----------------------------------
            "jobs_completed": 0,
            "collectors_invoked": 0,
            "live_source_calls": 0,
            "network_calls": 0,
            "last_checked_at_advanced": False,
            "source_monitoring_live": False,
        }
    )


def missed_window_invariant_failures(recovery: dict[str, Any]) -> list[str]:
    """Refuse a recovery that replayed too much, or double-counted."""
    fails: list[str] = list(recovery.get("invariant_failures") or [])

    per_slot = recovery.get("per_slot") or []
    if len(per_slot) != int(recovery.get("slots_offered") or 0) and recovery.get("ran"):
        fails.append("per_slot_does_not_account_for_every_offered_slot")

    counted_recovered = sum(1 for s in per_slot if s.get("result") == RECOVERED)
    if counted_recovered != int(recovery.get("slots_recovered") or 0):
        fails.append("slots_recovered_disagrees_with_the_per_slot_results")

    counted_already = sum(1 for s in per_slot if s.get("result") == ALREADY_SERVED)
    if counted_already != int(recovery.get("slots_already_served") or 0):
        fails.append("slots_already_served_disagrees_with_the_per_slot_results")

    counted_refused = sum(1 for s in per_slot if s.get("result") == REFUSED)
    if counted_refused != int(recovery.get("slots_refused") or 0):
        fails.append("slots_refused_disagrees_with_the_per_slot_results")

    for entry in per_slot:
        if entry.get("result") not in SLOT_RESULTS:
            fails.append(f"slot_result_outside_vocabulary:{entry.get('result')}")
        if entry.get("result") == RECOVERED and entry.get("blocked_reasons"):
            fails.append(f"recovered_slot_carries_refusals:{entry.get('slot_index')}")
        if entry.get("result") == ALREADY_SERVED and not entry.get(
            "blocked_reasons"
        ):
            fails.append(
                f"already_served_slot_named_no_reason:{entry.get('slot_index')}"
            )

    # A slot cannot be both recovered and already served.
    indexes = [entry.get("slot_index") for entry in per_slot]
    if len(indexes) != len(set(indexes)):
        fails.append("a_slot_appears_more_than_once_in_one_recovery")

    # The sums add up.
    total = (
        int(recovery.get("slots_recovered") or 0)
        + int(recovery.get("slots_already_served") or 0)
        + int(recovery.get("slots_refused") or 0)
    )
    if recovery.get("ran") and total != int(recovery.get("slots_offered") or 0):
        fails.append("recovered_plus_served_plus_refused_does_not_equal_offered")

    if bool(recovery.get("catchup_was_bounded")) is not (
        int(recovery.get("slots_dropped_by_the_bound") or 0) > 0
    ):
        fails.append("catchup_was_bounded_disagrees_with_the_dropped_count")

    # The standing boundary.
    for counter in (
        "jobs_completed",
        "collectors_invoked",
        "live_source_calls",
        "network_calls",
    ):
        if int(recovery.get(counter) or 0) != 0:
            fails.append(f"recovery_counted:{counter}={recovery.get(counter)}")
    if recovery.get("source_monitoring_live"):
        fails.append("recovery_claimed:source_monitoring_live")
    if recovery.get("last_checked_at_advanced"):
        fails.append("recovery_advanced_last_checked_at")

    return sorted(set(fails))
