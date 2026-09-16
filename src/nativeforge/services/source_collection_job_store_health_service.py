"""Job store health (Gate 158G).

## Readiness is not capability, and durability is not execution

This lane answers one question: *does queued collection work survive?* It does
not answer whether any of that work may run, and a green lane here means the
machinery kept its promises about persistence while contacting nothing.

```text
collection_job_store_ready = True    queued work survives a restart
jobs_completed              = 0      and nothing has been collected
source_monitoring_live      = False
```

Both halves have to stay sayable at once. Gate 155 measured the campaign's
recurring failure as declared-vs-derived; the shape it takes here would be a
store that reports itself ready and thereby implies a source was checked.

## Every condition is measured by somebody else

`build_job_store_health` receives results and reads them. It opens no
connection, enqueues nothing and transitions nothing, so it cannot pass its own
lane by doing the work it is grading - the Gate 144 rule about not grading your
own homework, applied to a health reporter.

`completed_unreachable` is the one condition derived rather than passed in: it
comes from `job_store_capability()`, which reads `transition_job`'s signature.
A caller cannot fake it by supplying a flag.

## A blocker closes the lane, whatever else is true

Gate 154 shipped a `ready` that weighed only the conditions it expected to
matter, so an unexpected failure was named in `blockers` and then ignored. Here
`ready` is `all(conditions) and not blockers`, so anything that lands in
`blockers` closes the lane.
"""

from __future__ import annotations

import json
from typing import Any

from nativeforge.repositories.source_collection_job_repository import (
    COMPLETED,
    LIVE_STATUSES,
    job_store_capability,
    job_store_invariant_failures,
)

SCHEMA_VERSION = "nf_source_collection_job_store_health_v1"

CONTROLLED_SCOPE = "controlled_dev_demo"

CONDITIONS: tuple[str, ...] = (
    "table_exists",
    "enqueue_is_idempotent",
    "survives_restart",
    "illegal_transition_refused",
    "completed_unreachable",
    "lifecycle_is_not_on_the_lease",
    "nothing_collected",
)

CONDITION_EVIDENCE: dict[str, str] = {
    "table_exists": "nf_source_collection_jobs, created by migration 0044",
    "enqueue_is_idempotent": (
        "the same slot enqueued twice produced one row, refused by a unique "
        "index rather than by a check with a race window in front of it"
    ),
    "survives_restart": (
        "a row written by one connection was read back by another after the "
        "writing connection closed, with its status unchanged. This one cannot "
        "be measured by a request: proving it needs a commit and a reconnect, "
        "and a GET that commits fixture rows is worse than a GET that defers. "
        "scripts/verify_nativeforge_collection_job_store.sh measures it."
    ),
    "illegal_transition_refused": (
        "a move outside the state machine was refused and the row was left "
        "alone, rather than coerced to the nearest legal state"
    ),
    "completed_unreachable": (
        "transition_job accepts no execution proof, and the database refuses a "
        "completed row whose execution_proof_ref is null. Derived from the "
        "function signature, not declared here."
    ),
    "lifecycle_is_not_on_the_lease": (
        "the job table declares no lease_owner, lease_acquired_at or "
        "lease_expires_at. Gate 157 owns the claim; a column that does not "
        "exist cannot drift from the table that owns it."
    ),
    "nothing_collected": (
        "zero completed rows and zero execution proofs, counted from the table "
        "rather than assumed from the absence of a collector"
    ),
}

#: Conditions a single request cannot measure without doing something worse
#: than not measuring them. Exported so the route names this list rather than
#: keeping its own copy, which is how the two would come to disagree.
NOT_MEASURABLE_BY_A_REQUEST: tuple[str, ...] = ("survives_restart",)

#: What this lane being green does not mean. Named, because a durable queue is
#: the most plausible thing to mistake for a working one.
READY_DOES_NOT_MEAN: tuple[str, ...] = (
    "a source was contacted",
    "a collector ran",
    "a source is approved",
    "source terms were accepted",
    "monitoring is live",
    "a job was completed",
)


def _json_safe(value: Any) -> Any:
    return json.loads(json.dumps(value, default=str, sort_keys=True))


def build_job_store_health(
    *,
    table_exists: Any = None,
    enqueue_result: dict[str, Any] | None = None,
    duplicate_enqueue_result: dict[str, Any] | None = None,
    reread_after_reconnect: dict[str, Any] | None = None,
    illegal_transition_result: dict[str, Any] | None = None,
    backlog: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Report the lane from results somebody else measured."""
    capability = job_store_capability()

    enqueued = enqueue_result or {}
    duplicated = duplicate_enqueue_result or {}
    reread = reread_after_reconnect or {}
    illegal = illegal_transition_result or {}
    counts = backlog or {}

    blockers: list[str] = []

    # Propagate every supplied result's own invariants. A lane that ignores the
    # invariant failures of its evidence is grading a summary, not the work.
    for label, payload in (
        ("enqueue", enqueued),
        ("duplicate_enqueue", duplicated),
        ("reread", reread),
        ("illegal_transition", illegal),
        ("backlog", counts),
    ):
        if payload:
            for failure in job_store_invariant_failures(payload):
                blockers.append(f"{label}:{failure}")

    # ---- the restart proof ------------------------------------------------
    #
    # Two conditions, deliberately: a row that came back is not a row that came
    # back unchanged, and a status that drifted across a reconnect would make
    # every other lifecycle claim meaningless.
    written_job = enqueued.get("job") or {}
    reread_job = reread.get("job") or {}
    # No reread supplied means nobody proved this, which is different from
    # having disproved it. Either way the condition is not met and the lane
    # does not go green - but `restart_evidence_supplied` says which it was,
    # so a red lane can be read as "unmeasured here" rather than "broken".
    restart_evidence_supplied = bool(reread)
    survived = bool(reread_job) and reread_job.get("status") == written_job.get(
        "status"
    )
    if reread_job and written_job and not survived:
        blockers.append(
            "a_row_changed_status_across_a_reconnect:"
            f"{written_job.get('status')}->{reread_job.get('status')}"
        )

    # ---- nothing collected, counted ---------------------------------------
    completed_rows = int(counts.get("completed_total") or 0)
    proof_rows = int(counts.get("rows_with_execution_proof") or 0)
    if completed_rows:
        blockers.append(f"the_store_holds_a_completed_job:{completed_rows}")
    if proof_rows:
        blockers.append(f"the_store_holds_an_execution_proof:{proof_rows}")

    by_status = counts.get("by_status") or {}

    measured = {
        "table_exists": bool(table_exists),
        # Created once, refused the second time. Both halves, or "idempotent"
        # would also be true of an enqueue that never inserted anything.
        "enqueue_is_idempotent": bool(
            enqueued.get("created") and duplicated.get("deduplicated")
        ),
        "survives_restart": survived,
        # Refused AND said why. A refusal with no reason is unfalsifiable.
        "illegal_transition_refused": bool(
            illegal and not illegal.get("transitioned") and illegal.get(
                "blocked_reasons"
            )
        ),
        "completed_unreachable": not capability["completed_is_reachable"],
        "lifecycle_is_not_on_the_lease": not capability["declares_lease_columns"],
        "nothing_collected": bool(counts) and completed_rows == 0 and proof_rows == 0,
    }

    missing = sorted(name for name, ok in measured.items() if not ok)
    blockers.extend(f"condition_not_met:{name}" for name in missing)

    # Any blocker closes the lane. Gate 154 shipped a `ready` that weighed only
    # the conditions it expected to matter, and then named a real failure in
    # `blockers` and ignored it.
    ready = all(measured.values()) and not blockers

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "scope": CONTROLLED_SCOPE,
            "collection_job_store_ready": ready,
            "conditions": measured,
            "conditions_expected": list(CONDITIONS),
            "condition_evidence": CONDITION_EVIDENCE,
            "conditions_not_met": missing,
            "restart_evidence_supplied": restart_evidence_supplied,
            "not_measurable_by_a_request": list(NOT_MEASURABLE_BY_A_REQUEST),
            "blockers": sorted(set(blockers)),
            "blocker_count": len(set(blockers)),
            # ---- what the store holds -----------------------------------
            "jobs_total": int(counts.get("total") or 0),
            "jobs_by_status": by_status,
            "jobs_live": int(counts.get("live_total") or 0),
            "jobs_completed": completed_rows,
            "rows_with_execution_proof": proof_rows,
            "oldest_live_job_queued_at": counts.get("oldest_queued_at"),
            "backlog_by_terminal_reason": counts.get("by_terminal_reason") or {},
            # ---- the boundary -------------------------------------------
            "ready_does_not_mean": list(READY_DOES_NOT_MEAN),
            "lifecycle_is_owned_by": capability["lifecycle_is_owned_by"],
            "claim_is_owned_by": capability["claim_is_owned_by"],
            "live_statuses": sorted(LIVE_STATUSES),
            "completed_status_name": COMPLETED,
            "collectors_invoked": 0,
            "live_source_calls": 0,
            "network_calls": 0,
            "urls_fetched": 0,
            "raw_payloads_written": 0,
            "emails_sent": 0,
            "object_store_calls": 0,
            "approved_source_count": 0,
            "source_monitoring_live": False,
        }
    )


def job_store_health_invariant_failures(health: dict[str, Any]) -> list[str]:
    """Refuse a health report that claims collection, or contradicts itself."""
    fails: list[str] = []

    for counter in (
        "collectors_invoked",
        "live_source_calls",
        "network_calls",
        "urls_fetched",
        "raw_payloads_written",
        "emails_sent",
        "object_store_calls",
        "approved_source_count",
        "jobs_completed",
        "rows_with_execution_proof",
    ):
        if int(health.get(counter) or 0) != 0:
            fails.append(f"health_counted:{counter}={health.get(counter)}")

    if health.get("source_monitoring_live"):
        fails.append("health_claimed:source_monitoring_live")

    # Ready alongside a blocker is the Gate 154 defect. Both directions.
    if health.get("collection_job_store_ready") and health.get("blockers"):
        fails.append("ready_alongside_blockers")
    if health.get("collection_job_store_ready") and health.get("conditions_not_met"):
        fails.append("ready_alongside_unmet_conditions")
    if not health.get("collection_job_store_ready") and not health.get("blockers"):
        fails.append("not_ready_without_naming_a_blocker")

    conditions = health.get("conditions") or {}
    expected = set(health.get("conditions_expected") or ())
    if expected and set(conditions) != expected:
        fails.append("conditions_do_not_match_the_declared_set")

    # Every condition carries its evidence, or a green lane is a green check
    # with no way to ask what it measured.
    evidence = health.get("condition_evidence") or {}
    for name in conditions:
        if not str(evidence.get(name) or "").strip():
            fails.append(f"condition_without_evidence:{name}")

    # The counts have to add up to the total they are reported beside.
    by_status = health.get("jobs_by_status") or {}
    if by_status and sum(by_status.values()) != int(health.get("jobs_total") or 0):
        fails.append("jobs_by_status_does_not_account_for_jobs_total")

    # A ready store that says it completed something is the exact confusion
    # this lane exists to prevent.
    if health.get("collection_job_store_ready"):
        if not health.get("ready_does_not_mean"):
            fails.append("ready_without_stating_what_ready_does_not_mean")
        if health.get("conditions", {}).get("completed_unreachable") is not True:
            fails.append("ready_while_completed_is_reachable")

    return sorted(set(fails))
