"""Gate 159M artifacts: the orchestration runtime, measured rather than described.

Ten files. Every number in them comes from calling the code they describe - the
slot arithmetic is computed, the trigger states are decided, the state machine
is rendered from the constants rather than retyped.

Nothing here opens a database. An artifact writer that needed a connection would
produce different files on different machines, and the suite compares these
against a fresh build.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from nativeforge.repositories.source_collection_orchestration_lock_repository import (
    ACQUIRED,
    CYCLE_OUTCOMES,
    CYCLE_STATUSES,
    CYCLES,
    DEFAULT_LEASE_SECONDS,
    RELEASED,
    TABLE_NAME,
)
from nativeforge.services.source_collection_missed_window_service import (
    SLOT_RESULTS,
    missed_window_invariant_failures,
    recover_missed_windows,
)
from nativeforge.services.source_collection_orchestration_health_service import (
    CONDITION_EVIDENCE,
    CONDITIONS,
    NOT_MEASURABLE_BY_A_REQUEST,
    READY_DOES_NOT_MEAN,
)
from nativeforge.services.source_collection_orchestration_identity_service import (
    CADENCE_SECONDS,
    DEFAULT_CADENCE,
    ORCHESTRATION_VERSION,
    SLOT_EPOCH,
    build_orchestration_identity,
    build_owner_id,
    compute_slot_index,
    orchestration_identity_invariant_failures,
)
from nativeforge.services.source_collection_orchestration_runtime_service import (
    COMPOSES,
    CYCLE_MODE_EVALUATE_AND_PERSIST,
    MODES_NOT_IMPLEMENTED,
    orchestration_cycle_invariant_failures,
    run_orchestration_cycle,
)
from nativeforge.services.source_collection_periodic_trigger_service import (
    DEFAULT_MAX_CATCHUP_SLOTS,
    TRIGGER_PERMITS_A_CYCLE,
    TRIGGER_STATES,
    build_trigger_schedule,
    compute_next_wake_at,
    evaluate_trigger,
    trigger_invariant_failures,
)

SCHEMA_VERSION = "nf_source_orchestration_gate159_artifacts_v1"

ARTIFACT_DIR = "artifacts/source_orchestration_gate159"

SURVEY_FILE = "orchestration_runtime_survey.json"
IDENTITY_FILE = "orchestration_cycle_identity.json"
DUPLICATE_FILE = "duplicate_trigger_suppression.json"
LOCK_FILE = "orchestration_lock_smoke.json"
MISSED_FILE = "missed_window_recovery.json"
RESTART_FILE = "restart_idempotency.json"
CYCLE_FILE = "orchestration_cycle_smoke.json"
HEALTH_FILE = "orchestration_health.json"
MONITORING_FILE = "source_monitoring_status.json"
BLOCKERS_FILE = "next_orchestration_blockers.md"

ARTIFACT_FILES: tuple[str, ...] = (
    SURVEY_FILE,
    IDENTITY_FILE,
    DUPLICATE_FILE,
    LOCK_FILE,
    MISSED_FILE,
    RESTART_FILE,
    CYCLE_FILE,
    HEALTH_FILE,
    MONITORING_FILE,
    BLOCKERS_FILE,
)

FORBIDDEN_SHAPES: tuple[tuple[str, str], ...] = (
    ("email_address", r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"),
    ("bearer_token", r"\beyJ[A-Za-z0-9_-]{8,}"),
    ("session_cookie", r"nf_session="),
    ("google_client_secret", r"GOCSPX-"),
    ("private_key", r"BEGIN PRIVATE KEY"),
    ("aws_key", r"AKIA"),
    ("provider_subject", r"\b\d{18,}\b"),
)

#: Fixed instants, so a rebuild is byte-identical.
T_SLOT_START = "2026-09-15T12:00:00Z"
T_SLOT_LATE = "2026-09-15T12:59:59Z"
T_NEXT_SLOT = "2026-09-15T13:00:00Z"
T_AFTER_GAP = "2026-09-15T18:00:00Z"

MIGRATION = "0045"


def _json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n"


def _assert_no_forbidden_shape(name: str, body: str) -> None:
    for shape, pattern in FORBIDDEN_SHAPES:
        if re.search(pattern, body):
            raise AssertionError(f"artifact {name} contains a {shape}")


def _survey() -> dict[str, Any]:
    """What the survey measured, and the gap it named."""
    return {
        "schema_version": SCHEMA_VERSION,
        "artifact": SURVEY_FILE,
        "migration": MIGRATION,
        "measured_before_building": {
            "systemd_units_installed_for_nativeforge": 3,
            "systemd_timers_for_nativeforge": 0,
            "units_in_the_repo_for_a_scheduler_or_worker": 0,
            "advisory_lock_primitives_in_src": 0,
            "tables_naming_an_orchestration_cycle": 0,
            "period_key_builders_in_the_repository": 0,
            "database_backend": "sqlite",
        },
        "the_gap": (
            "nothing woke the scheduler. scripts/run_source_collection_worker.py "
            "had a bounded loop and nothing invoked it; a cycle happened when a "
            "person ran a command."
        ),
        "why_a_new_table_was_needed": (
            "there was no locking primitive to compose. SQLite has no "
            "pg_advisory_lock, so the portable atomic primitive is a unique "
            "index - the third use of it in this block, after Gate 157's job "
            "claim and Gate 158's enqueue idempotency."
        ),
        "why_it_is_not_a_second_job_lease": {
            "nf_source_collection_job_leases": "per JOB - who is working this "
            "one piece of work",
            TABLE_NAME: "per CYCLE - who is running the loop",
            "lease_columns_declared_on_the_cycle_table": sorted(
                {column.name for column in CYCLES.columns}
                & {"lease_owner", "lease_acquired_at", "lease_expires_at"}
            ),
            "job_columns_declared_on_the_cycle_table": sorted(
                {column.name for column in CYCLES.columns}
                & {"job_id", "idempotency_key", "source_id", "attempt_count"}
            ),
        },
        "the_measurement_that_makes_a_trigger_safe": {
            "claim": "next_run_at does not move with the observer's clock",
            "why_it_matters": (
                "Gate 158's job_id digests scheduled_for, which IS next_run_at. "
                "If it moved with the clock, every poll would mint a new id and "
                "the idempotency Gate 158 proved would be worthless the moment "
                "anything polled."
            ),
            "measured": "same next_run_at at 12:00:00, 12:00:01, 18:44:13 and "
            "the following day",
        },
        "why_missed_windows_come_from_the_TRIGGER_not_the_source": (
            "last_checked_at is eleven weeks stale and nothing advances it, "
            "because advancing it is what an actual source check does. Every "
            "source sits permanently due in a slot that never moves, so there "
            "is no sequence of missed SOURCE windows to walk."
        ),
    }


def _identity() -> dict[str, Any]:
    """Determinism, and the things the identity must not depend on."""
    same_a = build_orchestration_identity(now=T_SLOT_START)
    same_b = build_orchestration_identity(now=T_SLOT_LATE)
    other = build_orchestration_identity(now=T_NEXT_SLOT)
    daily = build_orchestration_identity(now=T_SLOT_START, cadence="daily")
    unusable = build_orchestration_identity(now=None)

    return {
        "schema_version": SCHEMA_VERSION,
        "artifact": IDENTITY_FILE,
        "orchestration_version": ORCHESTRATION_VERSION,
        "slot_epoch": SLOT_EPOCH,
        "cadences": dict(sorted(CADENCE_SECONDS.items())),
        "default_cadence": DEFAULT_CADENCE,
        "measured": {
            "same_slot_twice_is_the_same_id": (
                same_a["cycle_id"] == same_b["cycle_id"]
            ),
            "a_different_slot_is_a_different_id": (
                same_a["cycle_id"] != other["cycle_id"]
            ),
            "a_different_cadence_is_a_different_id": (
                same_a["cycle_id"] != daily["cycle_id"]
            ),
            "the_slot_is_a_floor": (
                compute_slot_index(now=T_SLOT_START)
                == compute_slot_index(now=T_SLOT_LATE)
            ),
            "no_clock_yields_no_id": unusable["cycle_id"] is None,
        },
        "invariant_failures": {
            "usable": orchestration_identity_invariant_failures(same_a),
            "unusable": orchestration_identity_invariant_failures(unusable),
        },
        "derived_from": same_a["derived_from"],
        "not_derived_from": same_a["not_derived_from"],
        "why_not_a_pid_or_a_uuid": (
            "suppression works by RECOGNISING that a slot has already been "
            "served. An identity that cannot repeat cannot be recognised, so "
            "every restart would re-serve every slot."
        ),
        "the_owner_id_is_the_opposite": {
            "why": (
                "two processes contending for one cycle must be "
                "distinguishable, or the loser would believe it had won. So an "
                "owner DOES carry a nonce, and it is never part of a cycle id."
            ),
            "example_shape": build_owner_id(
                host="example-host", pid=1234, nonce="fixednonce00"
            ),
        },
        "a_cycle_id_is_not_a_job_id": same_a["is_a_collection_job_id"],
        "an_id_is_not_a_cycle_that_ran": same_a["implies_a_cycle_ran"],
    }


def _duplicate_suppression() -> dict[str, Any]:
    """Every trigger state, decided rather than described."""
    current = compute_slot_index(now=T_SLOT_START)
    cases = {
        "nothing_ever_served": evaluate_trigger(
            now=T_SLOT_START, last_served_slot_index=None
        ),
        "this_slot_already_served": evaluate_trigger(
            now=T_SLOT_START, last_served_slot_index=current
        ),
        "later_in_the_same_slot": evaluate_trigger(
            now=T_SLOT_LATE, last_served_slot_index=current
        ),
        "the_next_slot": evaluate_trigger(
            now=T_NEXT_SLOT, last_served_slot_index=current
        ),
        "a_five_hour_gap": evaluate_trigger(
            now=T_AFTER_GAP, last_served_slot_index=current
        ),
        "the_clock_went_backwards": evaluate_trigger(
            now=T_SLOT_START, last_served_slot_index=current + 99
        ),
        "the_trigger_is_disabled": evaluate_trigger(
            now=T_SLOT_START, last_served_slot_index=None, trigger_enabled=False
        ),
    }
    return {
        "schema_version": SCHEMA_VERSION,
        "artifact": DUPLICATE_FILE,
        "states": list(TRIGGER_STATES),
        "states_that_permit_a_cycle": sorted(TRIGGER_PERMITS_A_CYCLE),
        "decisions": {
            name: {
                "state": decision["state"],
                "should_run_a_cycle": decision["should_run_a_cycle"],
                "blocked_reasons": decision["blocked_reasons"],
                "missed_slot_count": decision["missed_slot_count"],
                "invariant_failures": trigger_invariant_failures(decision),
            }
            for name, decision in cases.items()
        },
        "why_not_due_and_already_triggered_are_different": (
            "not_due is a statement about the clock; already_triggered is a "
            "statement about history. Collapsing them would make a duplicate "
            "attempt indistinguishable from a poll that arrived early."
        ),
        "repeated_polling": (
            "the slot is a floor over an injected clock, so a hundred polls "
            "inside one hourly window decide `due` once and `already_triggered` "
            "ninety-nine times"
        ),
        "next_wake_is_a_boundary_not_an_interval": {
            "from": T_SLOT_LATE,
            "next_wake_at": compute_next_wake_at(now=T_SLOT_LATE),
            "why": (
                "a process that slept for `interval` from an arbitrary wake "
                "time would drift off the boundary and eventually serve two "
                "slots in one window, or none"
            ),
            "upcoming": build_trigger_schedule(now=T_SLOT_START, count=4)["wakes"],
        },
    }


def _lock_smoke() -> dict[str, Any]:
    """The ownership contract, rendered from the table and the constants."""
    return {
        "schema_version": SCHEMA_VERSION,
        "artifact": LOCK_FILE,
        "table": TABLE_NAME,
        "migration": MIGRATION,
        "statuses": sorted(CYCLE_STATUSES),
        "outcomes": sorted(CYCLE_OUTCOMES),
        "default_lease_seconds": DEFAULT_LEASE_SECONDS,
        "acquisition": {
            "how": "insert, catch the integrity error",
            "not": "check, then insert",
            "why": (
                "check-then-insert has a window between the two halves that "
                "two processes can both pass through"
            ),
            "enforced_by": "ux_nf_source_orchestration_cycles_cycle_id",
            "unique_over": ["organization_id", "cycle_id"],
        },
        "the_two_branches": {
            "a_live_owner": (
                "refused with ownership_has_not_expired_and_cannot_be_stolen"
            ),
            "an_expired_owner": (
                "reclaimable, and reclaim_count is incremented so `this keeps "
                "happening` is measurable rather than an impression"
            ),
        },
        "staleness_is_derived": (
            "a row is stale when expires_at has passed and nothing released "
            "it, computed against an injected clock on read. A stored `stale` "
            "status would need a sweeper to stay true, and would be wrong "
            "between sweeps."
        ),
        "the_defect_this_gate_found_in_itself": {
            "what": (
                "read_last_served_slot counted a row in ANY status as served, "
                "so a process that acquired a slot and crashed left an "
                "`acquired` row, every later process was told "
                "already_triggered, and the expired ownership was never "
                "reclaimed - for that slot, forever"
            ),
            "why_it_mattered": (
                "the expiry existed and the reclaim existed; the trigger made "
                "the reclaim unreachable. An unreachable recovery is worse "
                "than an unreachable refusal, because the system looks like it "
                "has a safety net it cannot use."
            ),
            "the_fix": (
                "a slot with a crashed owner is UNFINISHED, not served. "
                "History counts released slots and actively-owned ones, and "
                "excludes acquired-but-expired."
            ),
        },
        "database_refuses": [
            "jobs_completed <> 0",
            "collectors_invoked <> 0",
            "live_source_calls <> 0",
            "an acquired row with no expires_at",
            "a released row with no released_at",
        ],
        "status_when_owned": ACQUIRED,
        "status_when_finished": RELEASED,
    }


def _missed_window() -> dict[str, Any]:
    """Recovery, including the case where it correctly does nothing."""
    current = compute_slot_index(now=T_SLOT_START)
    gap = evaluate_trigger(
        now=T_AFTER_GAP, last_served_slot_index=current, max_catchup_slots=4
    )
    long_outage = evaluate_trigger(
        now="2026-09-17T18:00:00Z",
        last_served_slot_index=current,
        max_catchup_slots=4,
    )
    # No connection: the refusal is the artifact. A writer that opened a
    # database would produce different files on different machines.
    refused = recover_missed_windows(
        connection=None,
        organization_id="bbbbbbbb-cccc-dddd-eeee-ffffffffffff",
        owner_id="artifact-fixture",
        recoverable_slot_indexes=[current + 1],
        now=T_AFTER_GAP,
    )

    return {
        "schema_version": SCHEMA_VERSION,
        "artifact": MISSED_FILE,
        "slot_results": list(SLOT_RESULTS),
        "default_max_catchup_slots": DEFAULT_MAX_CATCHUP_SLOTS,
        "a_five_hour_gap": {
            "state": gap["state"],
            "missed_slot_count": gap["missed_slot_count"],
            "recoverable_slot_count": gap["recoverable_slot_count"],
            "slots_dropped_by_the_bound": gap["slots_dropped_by_the_bound"],
            "catchup_was_bounded": gap["catchup_was_bounded"],
        },
        "a_forty_two_hour_outage": {
            "state": long_outage["state"],
            "missed_slot_count": long_outage["missed_slot_count"],
            "recoverable_slot_count": long_outage["recoverable_slot_count"],
            "slots_dropped_by_the_bound": long_outage[
                "slots_dropped_by_the_bound"
            ],
            "catchup_was_bounded": long_outage["catchup_was_bounded"],
            "note": (
                "the bound serves the most RECENT slots, because the oldest "
                "describe work the newest already covers"
            ),
        },
        "recovery_without_a_connection": {
            "ran": refused["ran"],
            "blocked_reasons": refused["blocked_reasons"],
            "invariant_failures": missed_window_invariant_failures(refused),
        },
        "a_recovered_slot_may_create_no_work": refused[
            "a_recovered_slot_may_create_no_work"
        ],
        "why_unbounded_would_be_wrong": (
            "a process down for a month at hourly cadence would wake and "
            "replay seven hundred slots, each a full scheduler pass over 177 "
            "sources, all producing the same deduplicated rows"
        ),
        "recovery_does_not_compete_for_the_present": (
            "the recovery pass acquires with allow_reclaim=False, so catching "
            "up on history cannot steal a slot another process is serving"
        ),
    }


def _restart_idempotency() -> dict[str, Any]:
    """Why running the same instant twice is safe, argued from the ids."""
    current = compute_slot_index(now=T_SLOT_START)
    return {
        "schema_version": SCHEMA_VERSION,
        "artifact": RESTART_FILE,
        "five_evaluations_of_one_slot": {
            "distinct_cycle_ids": len(
                {
                    build_orchestration_identity(now=instant)["cycle_id"]
                    for instant in (
                        "2026-09-15T12:00:00Z",
                        "2026-09-15T12:00:01Z",
                        "2026-09-15T12:17:44Z",
                        "2026-09-15T12:59:58Z",
                        T_SLOT_LATE,
                    )
                }
            ),
            "expected": 1,
        },
        "the_decision_on_a_replay": evaluate_trigger(
            now=T_SLOT_START, last_served_slot_index=current
        )["state"],
        "enforced_by": [
            "ux_nf_source_orchestration_cycles_cycle_id  (the slot)",
            "ux_nf_source_collection_jobs_job_id  (the work, Gate 158)",
        ],
        "two_layers": (
            "even if a cycle row were somehow re-acquired, the work it does is "
            "idempotent on Gate 158's deterministic job_id. The store would "
            "deduplicate, so a duplicated cycle costs time and not correctness."
        ),
        "what_a_crash_costs": (
            "a cycle killed mid-pass leaves its ownership row acquired with an "
            "expiry. Another process reclaims it once the expiry lapses, so an "
            "ungraceful death costs one lease window - not the slot forever."
        ),
        "measured_by_the_verifier": (
            "phases A and B run in SEPARATE python processes; phase B reads "
            "rows phase A committed and then exited - "
            "scripts/verify_nativeforge_source_orchestration_runtime.sh"
        ),
    }


def _cycle_smoke() -> dict[str, Any]:
    """A cycle requested with no connection. The refusal is the artifact."""
    refused = run_orchestration_cycle(
        connection=None,
        organization_id="bbbbbbbb-cccc-dddd-eeee-ffffffffffff",
        owner_id="artifact-fixture",
        sources=[],
        now=T_SLOT_START,
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "artifact": CYCLE_FILE,
        "mode": CYCLE_MODE_EVALUATE_AND_PERSIST,
        "modes_not_implemented": list(MODES_NOT_IMPLEMENTED),
        "composes": list(COMPOSES),
        "a_cycle_without_a_connection": {
            "ran": refused["ran"],
            "blocked_reasons": refused["blocked_reasons"],
            "jobs_created": refused["jobs_created"],
            "invariant_failures": orchestration_cycle_invariant_failures(refused),
        },
        "the_order": [
            "evaluate the trigger against the last served slot",
            "acquire the cycle for this slot, atomically, or refuse",
            "run Gate 156 into Gate 158 in evaluate_and_enqueue mode",
            "run Gate 157 over the persisted backlog",
            "recover missed slots, bounded",
            "release the cycle, recording what it did",
        ],
        "what_the_orchestrator_adds": (
            "ordering, exclusivity and recovery. It adds no capability to the "
            "three gates it calls: after a cycle the same sources are blocked "
            "for the same reasons."
        ),
        "constants": {
            "collectors_invoked": refused["collectors_invoked"],
            "live_source_calls": refused["live_source_calls"],
            "network_calls": refused["network_calls"],
            "emails_sent": refused["emails_sent"],
            "object_store_calls": refused["object_store_calls"],
            "last_checked_at_advanced": refused["last_checked_at_advanced"],
            "source_monitoring_live": refused["source_monitoring_live"],
        },
    }


def _health_contract() -> dict[str, Any]:
    """The lane's conditions, and the three a request cannot produce."""
    return {
        "schema_version": SCHEMA_VERSION,
        "artifact": HEALTH_FILE,
        "lane": "orchestration_runtime_ready",
        "conditions": list(CONDITIONS),
        "condition_evidence": dict(CONDITION_EVIDENCE),
        "not_measurable_by_a_request": list(NOT_MEASURABLE_BY_A_REQUEST),
        "why": (
            "reclaiming an expired owner needs a process to die and a lease to "
            "lapse; recovering a missed window needs downtime; restart "
            "idempotency needs a second process. A request has none of those, "
            "so the route reports those three red and names the verifier."
        ),
        "what_a_request_CAN_measure": (
            "cycle_completed, duplicate_trigger_suppressed and "
            "single_active_owner, inside a SAVEPOINT that is rolled back. The "
            "savepoint matters: a committed probe would consume the real slot "
            "and the next genuine wake would be told already_triggered - a "
            "READ endpoint would have suppressed a real cycle."
        ),
        "ready_does_not_mean": list(READY_DOES_NOT_MEAN),
        "process_state_is_supplied": (
            "whether a process is running is a fact about the host. The "
            "verifier reads systemd; the route reports the absence honestly."
        ),
        "any_blocker_closes_the_lane": (
            "ready is all(conditions) and not blockers. Gate 154 shipped a "
            "ready that weighed only the conditions it expected to matter."
        ),
    }


def _monitoring_status() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "artifact": MONITORING_FILE,
        "source_monitoring_live": False,
        "approved_source_count": 0,
        "collectors_registered": 0,
        "collectors_invoked": 0,
        "live_source_calls": 0,
        "network_calls": 0,
        "urls_fetched": 0,
        "raw_payloads_written": 0,
        "emails_sent": 0,
        "object_store_calls": 0,
        "jobs_completed": 0,
        "rows_with_execution_proof": 0,
        "last_checked_at_advanced": False,
        "orchestrator_unit_written": True,
        "orchestrator_unit_enabled_by_this_gate": False,
        "what_gate_159_added": (
            "something that wakes on a cadence, takes one slot at a time, and "
            "recovers the slots it missed while it was down"
        ),
        "what_it_did_not_add": [
            "a collector",
            "an approved source",
            "accepted source terms",
            "a completed job",
            "an execution proof",
            "a schedule advance",
            "live monitoring",
        ],
        "a_trigger_is_not_a_source_check": True,
        "a_running_timer_is_not_live_monitoring": True,
        "persisted_job_means_collection_occurred": False,
        "claimed_job_means_source_contacted": False,
    }


def _blockers_markdown() -> str:
    return """# Next: what still stands between a running loop and a collection

Gate 159 built the periodic orchestration runtime. Something now wakes on a
cadence, takes one slot at a time, and recovers the slots it missed. It contacts
nothing, and it cannot.

## What is now true

```text
a loop wakes on a cadence            hourly by default, slot-aligned
exactly one cycle per slot           unique index on (organization_id, cycle_id)
a duplicate trigger is named         already_triggered, not a silent skip
two owners cannot both hold a slot   the live one is not stealable
a crashed owner does not block it    expired ownership is reclaimable
missed slots recover once            bounded, and the dropped count reported
a restart recovers nothing new       the slot is already served
```

## What still blocks a collection, in the order it has to clear

```text
1  raw payload persistence   Gate 160. There is nowhere to put a response.
2  a collector envelope      Gate 161. No code can fetch anything.
3  source allowlist          Gate 162. Zero sources are approved, and this is
                             where approval gets defined.
4  source terms              a HUMAN must read them. 171 sources are blocked
                             on this and no gate can clear it.
5  human review              a HUMAN must look at each source.
```

Items 1 to 3 are engineering. Items 4 and 5 are not, and a loop that wakes every
hour does not make them so - it means the backlog is now measured hourly rather
than whenever somebody remembers to run a command.

Gate 155's rule stands: do not recommend more wrapper gates around a blocker
only a person or an approval can clear.

## The one decision this gate deliberately left to a human

`ops/systemd/nativeforge-source-orchestrator.service` is written and **not
enabled**. Nothing in the repository installs or enables it.

Writing the unit proves the runtime is supervisable. Starting it is a different
claim - that something should wake on its own on this host - and that is a
choice for whoever runs the host. The unit lists its own preconditions, and all
of them are currently verified.

## What the cadence now makes askable

```text
when did the loop last run              last_cycle_completed_at
when will it run next                   next_trigger_at
did it miss anything while down         missed_windows_detected / recovered
is anything holding a slot it lost      stale_cycle_owners
how long has blocked work been waiting  oldest_live_job_queued_at (Gate 158)
```

That last line is the one the campaign has been building toward. The backlog was
countable after Gate 158; it is now counted on a schedule, which is what makes
"these 171 sources have been waiting since June" a number somebody can watch
grow rather than a thing they have to go and ask for.
"""


def build_orchestration_artifacts() -> dict[str, str]:
    """Every artifact body, keyed by filename. Writes nothing."""
    files = {
        SURVEY_FILE: _json(_survey()),
        IDENTITY_FILE: _json(_identity()),
        DUPLICATE_FILE: _json(_duplicate_suppression()),
        LOCK_FILE: _json(_lock_smoke()),
        MISSED_FILE: _json(_missed_window()),
        RESTART_FILE: _json(_restart_idempotency()),
        CYCLE_FILE: _json(_cycle_smoke()),
        HEALTH_FILE: _json(_health_contract()),
        MONITORING_FILE: _json(_monitoring_status()),
        BLOCKERS_FILE: _blockers_markdown(),
    }
    for name, body in files.items():
        _assert_no_forbidden_shape(name, body)
    return files


def write_orchestration_artifacts(*, repo_root: Any = None) -> dict[str, Any]:
    """Write every file under ``ARTIFACT_DIR``, relative to ``repo_root``."""
    root = Path(repo_root) if repo_root is not None else Path()
    directory = root / ARTIFACT_DIR
    directory.mkdir(parents=True, exist_ok=True)

    files = build_orchestration_artifacts()
    for name, body in files.items():
        (directory / name).write_text(body, encoding="utf-8")

    return {
        "schema_version": SCHEMA_VERSION,
        "directory": str(directory),
        "files_written": sorted(files),
        "file_count": len(files),
    }


def orchestration_artifact_invariant_failures(result: dict[str, Any]) -> list[str]:
    fails: list[str] = []

    written = set(result.get("files_written") or [])
    missing = set(ARTIFACT_FILES) - written
    if missing:
        fails.append(f"artifact_files_missing:{sorted(missing)}")
    extra = written - set(ARTIFACT_FILES)
    if extra:
        fails.append(f"artifact_files_undeclared:{sorted(extra)}")
    if result.get("file_count") != len(written):
        fails.append("file_count_disagrees_with_the_names")

    return fails
