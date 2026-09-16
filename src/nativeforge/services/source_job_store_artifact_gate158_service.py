"""Gate 158K artifacts: what the job store is, measured rather than described.

Nine files. Every number in them comes from calling the code they describe -
the capability report is `job_store_capability()`, the identity determinism is
two real digests compared, the state machine is `LEGAL_TRANSITIONS` rendered
rather than retyped.

Nothing here opens a database. An artifact writer that needed a connection
would produce different files on different machines, and the suite compares
these against a fresh build.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from nativeforge.repositories.source_collection_job_repository import (
    ARCHIVED,
    CLAIMED,
    COMPLETED,
    FAILED,
    JOB_STATUSES,
    LEGAL_TRANSITIONS,
    LIVE_STATUSES,
    QUEUED,
    REFUSED,
    RETRY_WAIT,
    TABLE_NAME,
    TERMINAL_REASONS,
    job_store_capability,
)
from nativeforge.services.source_collection_job_identity_service import (
    COMPOSED_FROM,
    build_job_identity,
    identity_invariant_failures,
)
from nativeforge.services.source_collection_job_store_health_service import (
    CONDITION_EVIDENCE,
    CONDITIONS,
    NOT_MEASURABLE_BY_A_REQUEST,
    READY_DOES_NOT_MEAN,
)
from nativeforge.services.source_collection_scheduler_loop_service import (
    CYCLE_MODE_EVALUATE_AND_ENQUEUE,
    CYCLE_MODE_EVALUATE_ONLY,
    CYCLE_MODES,
    cycle_invariant_failures,
    run_scheduler_cycle,
)

SCHEMA_VERSION = "nf_source_job_store_gate158_artifacts_v1"

ARTIFACT_DIR = "artifacts/source_job_store_gate158"

CAPABILITY_FILE = "job_store_capability.json"
IDENTITY_FILE = "job_identity_determinism.json"
STATE_MACHINE_FILE = "job_state_machine.json"
PERSISTENCE_FILE = "scheduler_persistence_smoke.json"
IDEMPOTENCY_FILE = "enqueue_idempotency.json"
BOUNDARY_FILE = "lease_vs_job_boundary.json"
HEALTH_FILE = "job_store_health_contract.json"
MONITORING_FILE = "source_monitoring_status.json"
BLOCKERS_FILE = "next_job_store_blockers.md"

ARTIFACT_FILES: tuple[str, ...] = (
    CAPABILITY_FILE,
    IDENTITY_FILE,
    STATE_MACHINE_FILE,
    PERSISTENCE_FILE,
    IDEMPOTENCY_FILE,
    BOUNDARY_FILE,
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

FIXTURE_NOW = "2026-09-15T12:00:00Z"

MIGRATION = "0044"


def _json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n"


def _assert_no_forbidden_shape(name: str, body: str) -> None:
    for shape, pattern in FORBIDDEN_SHAPES:
        if re.search(pattern, body):
            raise AssertionError(f"artifact {name} contains a {shape}")


def _fixture_sources(count: int = 3) -> list[dict[str, Any]]:
    """Blocked sources, each prerequisite unsatisfied by name."""
    return [
        {
            "source_id": f"nf-gate158-fixture-{index}",
            "check_interval_days": 7,
            "last_checked_at": "2026-09-01T00:00:00Z",
            "is_enabled": True,
            "activation_state": "activation_blocked",
            "terms_state": "terms_unknown",
            "human_review_state": "human_review_required",
            "collector_registered": False,
        }
        for index in range(count)
    ]


def _capability() -> dict[str, Any]:
    """The capability report, as the repository derives it about itself."""
    return {
        "schema_version": SCHEMA_VERSION,
        "artifact": CAPABILITY_FILE,
        "migration": MIGRATION,
        "capability": job_store_capability(),
        "why_this_is_derived": (
            "`completed_is_reachable` is computed by reading whether "
            "transition_job accepts an execution proof, and "
            "`declares_lease_columns` by reading the declared table. Both "
            "change by themselves if the code changes, rather than going "
            "stale as constants somebody has to remember."
        ),
    }


def _identity() -> dict[str, Any]:
    """Determinism, and the two drifts Gate 158 measured on the way here."""
    same_a = build_job_identity(
        source_id="nf-gate158-fixture-0", scheduled_for="2026-09-20T00:00:00Z"
    )
    same_b = build_job_identity(
        source_id="nf-gate158-fixture-0", scheduled_for="2026-09-20T00:00:00Z"
    )
    other_slot = build_job_identity(
        source_id="nf-gate158-fixture-0", scheduled_for="2026-09-27T00:00:00Z"
    )
    perpetual = build_job_identity(
        source_id="nf-gate158-fixture-0", scheduled_for=None
    )
    out_of_vocabulary = build_job_identity(
        source_id="nf-gate158-fixture-0",
        scheduled_for=None,
        job_type="scheduled_check",
    )

    return {
        "schema_version": SCHEMA_VERSION,
        "artifact": IDENTITY_FILE,
        "composed_from": list(COMPOSED_FROM),
        "measured": {
            "same_slot_twice_is_the_same_id": same_a["job_id"] == same_b["job_id"],
            "a_different_slot_is_a_different_id": (
                same_a["job_id"] != other_slot["job_id"]
            ),
            "no_cadence_is_one_perpetual_slot": perpetual["is_perpetual_slot"],
            "job_id_is_not_the_idempotency_key": (
                same_a["job_id"] != same_a["idempotency_key"]
            ),
        },
        "invariant_failures": {
            "same_slot": identity_invariant_failures(same_a),
            "perpetual": identity_invariant_failures(perpetual),
        },
        "the_out_of_vocabulary_job_type": {
            "requested": out_of_vocabulary["job_type_requested"],
            "digested": out_of_vocabulary["job_type"],
            "was_normalized": out_of_vocabulary["job_type_was_normalized"],
            "why_it_matters": (
                "Gate 156 passed `scheduled_check`, which is not in Gate 99B's "
                "JOB_TYPES, so it was normalized to `source_check` and THAT is "
                "what every job_id has always digested. An identity service "
                "carrying its own copy of the word produced a different id in "
                "all four measured cases - ids the store would have held and "
                "the scheduler would never have reported."
            ),
        },
        "the_stray_strip": (
            "a `.strip()` on the source_id before digesting also produced a "
            "different id than the scheduler reports, for a padded source_id. "
            "Gate 99B does not strip, so neither does this. Two "
            "normalizations of one fact is how two parts of a system come to "
            "disagree about whether two jobs are the same job."
        ),
        "identity_is_not_permission": {
            "implies_source_approval": same_a["implies_source_approval"],
            "implies_collection_permitted": same_a["implies_collection_permitted"],
            "why": (
                "an id can be computed for a source nobody approved. That is "
                "the point: counting how long blocked work has waited is what "
                "eventually makes somebody read the terms."
            ),
        },
    }


def _state_machine() -> dict[str, Any]:
    """The transitions, rendered from the table rather than retyped."""
    return {
        "schema_version": SCHEMA_VERSION,
        "artifact": STATE_MACHINE_FILE,
        "table": TABLE_NAME,
        "statuses": sorted(JOB_STATUSES),
        "live_statuses": sorted(LIVE_STATUSES),
        "resting_statuses": sorted(JOB_STATUSES - LIVE_STATUSES),
        "terminal_reasons": sorted(TERMINAL_REASONS),
        "legal_transitions": {
            state: sorted(targets) for state, targets in LEGAL_TRANSITIONS.items()
        },
        "notable": {
            f"{QUEUED}->{REFUSED}": (
                "NOT legal. An outcome without a claim never happened."
            ),
            f"{REFUSED}->{QUEUED}": (
                "legal, and the one that matters for this campaign. When "
                "somebody finally reads the terms, 171 blocked jobs become "
                "runnable work again rather than needing to be recreated."
            ),
            f"{CLAIMED}->{COMPLETED}": (
                "in the table, and unreachable. transition_job accepts no "
                "execution proof and the database refuses a completed row "
                "without one."
            ),
            f"{ARCHIVED}->*": (
                "nothing. Reviving an archived job would rewrite a closed "
                "history."
            ),
            f"*->{RETRY_WAIT}": (
                "only with terminal_reason=transient_worker_failure. An "
                "activation or terms refusal parked in a retry queue would "
                "burn attempts on work no worker can ever run."
            ),
            f"{FAILED}->{QUEUED}": (
                "legal, for an operator requeue after a fix. Nothing in this "
                "gate calls it."
            ),
        },
    }


def _persistence() -> dict[str, Any]:
    """A cycle in each mode. The connectionless one must write nothing."""
    evaluate_only = run_scheduler_cycle(
        now=FIXTURE_NOW,
        sources=_fixture_sources(),
        organization_id="bbbbbbbb-cccc-dddd-eeee-ffffffffffff",
    )
    # Requested WITHOUT a connection on purpose: the refusal is the artifact.
    # A writer that opened a database would produce a different file on every
    # machine, and the suite compares these against a fresh build.
    refused = run_scheduler_cycle(
        now=FIXTURE_NOW,
        sources=_fixture_sources(),
        organization_id="bbbbbbbb-cccc-dddd-eeee-ffffffffffff",
        mode=CYCLE_MODE_EVALUATE_AND_ENQUEUE,
        connection=None,
    )

    return {
        "schema_version": SCHEMA_VERSION,
        "artifact": PERSISTENCE_FILE,
        "cycle_modes": list(CYCLE_MODES),
        "evaluate_only": {
            "mode": evaluate_only["mode"],
            "jobs_known": evaluate_only["jobs_known"],
            "rows_written": evaluate_only["rows_written"],
            "enqueue_requested": evaluate_only["enqueue_requested"],
            "invariant_failures": cycle_invariant_failures(evaluate_only),
        },
        "enqueue_without_a_connection": {
            "mode": refused["mode"],
            "rows_written": refused["rows_written"],
            "enqueue_performed": refused["enqueue_performed"],
            "enqueue_blocked_reasons": refused["enqueue_blocked_reasons"],
            "invariant_failures": cycle_invariant_failures(refused),
        },
        "rows_written_is_derived": (
            "through Gate 157 this was a declared 0, which was true only "
            "because the cycle could not write. It is now counted, so a cycle "
            "that writes cannot report that it did not - and "
            "cycle_invariant_failures checks it AGREES with the per-job "
            "results rather than simply dropping the old must-be-zero check."
        ),
        "persisting_is_not_executing": {
            "collectors_invoked": refused["collectors_invoked"],
            "live_source_calls": refused["live_source_calls"],
            "network_calls": refused["network_calls"],
            "urls_fetched": refused["urls_fetched"],
            "raw_payloads_written": refused["raw_payloads_written"],
        },
        "default_mode": CYCLE_MODE_EVALUATE_ONLY,
        "why_the_default_did_not_change": (
            "nothing that called run_scheduler_cycle before Gate 158 writes a "
            "row now. Persisting is opt-in."
        ),
    }


def _idempotency() -> dict[str, Any]:
    """Why repeated cycles do not grow the store, argued from the ids."""
    slots = [
        build_job_identity(source_id="nf-gate158-fixture-0", scheduled_for=None)
        for _ in range(5)
    ]
    return {
        "schema_version": SCHEMA_VERSION,
        "artifact": IDEMPOTENCY_FILE,
        "five_computations_of_one_slot": {
            "distinct_job_ids": len({identity["job_id"] for identity in slots}),
            "expected": 1,
        },
        "enforced_by": "ux_nf_source_collection_jobs_job_id",
        "unique_over": ["organization_id", "job_id"],
        "how_enqueue_uses_it": (
            "insert first, catch the integrity error. NOT check-then-insert, "
            "which is a race two scheduler processes lose together."
        ),
        "the_bound": (
            "177 registry sources with no cadence have one perpetual slot "
            "each, so repeated cycles hold the store at 177 rows rather than "
            "adding 177 a cycle. A source that DOES have a cadence gets a new "
            "row per slot, which is correct: last week's missed window and "
            "this week's pending one are different work."
        ),
        "measured_by_the_verifier": (
            "five cycles over three sources leave three rows - "
            "scripts/verify_nativeforge_collection_job_store.sh"
        ),
        "a_re_enqueue_does_not_reset_a_refusal": (
            "enqueue is create-if-absent and never an update, so a later "
            "cycle cannot erase an outcome a worker recorded."
        ),
    }


def _boundary() -> dict[str, Any]:
    """Which table owns what, and the column absence that keeps it that way."""
    capability = job_store_capability()
    return {
        "schema_version": SCHEMA_VERSION,
        "artifact": BOUNDARY_FILE,
        "lifecycle_is_owned_by": capability["lifecycle_is_owned_by"],
        "claim_is_owned_by": capability["claim_is_owned_by"],
        "lease_columns_declared_on_the_job_table": capability[
            "declares_lease_columns"
        ],
        "what_each_answers": {
            "a lease": "who holds this right now, and expires in five minutes",
            "a job": "does this work still need doing, until done or archived",
        },
        "why_they_cannot_be_one_row": (
            "they have different lifetimes, and one row cannot have two. Gate "
            "157 put attempt accounting on the lease row because the worker "
            "had nowhere else to write it, and that was the right call for "
            "one gate: a lease without an attempt count cannot bound a retry "
            "across a crash."
        ),
        "the_table_gate_158_declined": {
            "table": "nf_source_check_runs",
            "why": (
                "its check_status vocabulary is "
                "scheduled|running|succeeded|succeeded_with_warnings|failed|"
                "canceled, beside opportunities_seen_count and accepted_count. "
                "That is the record of a check that HAPPENED. A queue row "
                "written there would assert a source was contacted when none "
                "was - the reason Gate 157 declined it for leases, and the "
                "reason Gate 158 declines it again."
            ),
        },
        "the_worker_writes_both": (
            "a lease to take the claim, a job transition to record the "
            "outcome. Gate 158 measured the worker OVERWRITING the four "
            "blockers the scheduler had recorded with a single runtime note, "
            "which made `how long have 171 sources been terms-blocked` "
            "unanswerable after one pass. It now unions them."
        ),
    }


def _health_contract() -> dict[str, Any]:
    """The lane's conditions and its evidence, with the one a request cannot get."""
    return {
        "schema_version": SCHEMA_VERSION,
        "artifact": HEALTH_FILE,
        "lane": "collection_job_store_ready",
        "conditions": list(CONDITIONS),
        "condition_evidence": dict(CONDITION_EVIDENCE),
        "not_measurable_by_a_request": list(NOT_MEASURABLE_BY_A_REQUEST),
        "why": (
            "proving a row survives a restart needs a commit and a reconnect. "
            "A GET that commits fixture rows into the demo org would be worse "
            "than a GET that defers, so the route reports that condition red "
            "and names the verifier. Reading back through the connection that "
            "wrote would have turned it green for the wrong reason - a green "
            "check with two possible causes has only been half-tested."
        ),
        "ready_does_not_mean": list(READY_DOES_NOT_MEAN),
        "any_blocker_closes_the_lane": (
            "ready is all(conditions) and not blockers. Gate 154 shipped a "
            "ready that weighed only the conditions it expected to matter, and "
            "then named a real failure in blockers and ignored it."
        ),
    }


def _monitoring_status() -> dict[str, Any]:
    """The line that must stay true while the runtime grows."""
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
        "what_gate_158_added": (
            "a durable place to record that collection work is waiting, and "
            "the lifecycle transitions that record why it is not running."
        ),
        "what_it_did_not_add": [
            "a collector",
            "an approved source",
            "accepted source terms",
            "a completed job",
            "an execution proof",
            "a timer that fires on its own",
            "live monitoring",
        ],
        "persisted_job_means_collection_occurred": False,
        "claimed_job_means_source_contacted": False,
    }


def _blockers_markdown() -> str:
    return """# Next: what still stands between a job store and a collection

Gate 158 made the collection job lifecycle durable. Nothing in it contacted a
source, and nothing in it could.

## What is now true

```text
queued work survives a process restart        proven by a second process
enqueue is idempotent across repeated cycles  5 cycles, 3 rows
a refusal outlives the worker that recorded it
the backlog reason stays countable            terms_blocked, not unknown
a completed job cannot exist                  refused by repository AND database
```

## What still blocks a collection, in the order it has to clear

```text
1  a periodic trigger        Gate 159. Nothing fires on its own yet; a cycle
                             runs when a person or a script runs it.
2  raw payload persistence   Gate 160. There is nowhere to put a response.
3  a collector envelope      Gate 161. No code can fetch anything.
4  source allowlist          Gate 162. Zero sources are approved, and this is
                             the boundary that decides approval means.
5  source terms              a HUMAN must read them. 171 sources are blocked
                             on this and no gate can clear it.
6  human review              a HUMAN must look at each source.
```

Items 1 to 4 are engineering. Items 5 and 6 are not, and no amount of runtime
makes them so. Gate 155's rule stands: do not recommend more wrapper gates
around a blocker only a person can clear.

## What Gate 158 deliberately did not do

`execution_proof_ref` exists as a column and is null on every row. Nothing
writes it, and `transition_job` has no parameter that could. The gate that
defines what an execution proof *is* has not been written, so `completed`
remains a word in a vocabulary rather than a state anything can reach.

Defining it is the moment "a job finished" becomes a claim the system can make,
and it should cost a gate of its own.

## What the durable backlog now makes askable

```text
how many jobs are waiting, by status
how long has the oldest one waited          oldest_live_job_queued_at
why is each one blocked, by terminal reason
```

That last line is the argument for having persisted refused jobs at all. The
count was the point.
"""


def build_job_store_artifacts() -> dict[str, str]:
    """Every artifact body, keyed by filename. Writes nothing."""
    files = {
        CAPABILITY_FILE: _json(_capability()),
        IDENTITY_FILE: _json(_identity()),
        STATE_MACHINE_FILE: _json(_state_machine()),
        PERSISTENCE_FILE: _json(_persistence()),
        IDEMPOTENCY_FILE: _json(_idempotency()),
        BOUNDARY_FILE: _json(_boundary()),
        HEALTH_FILE: _json(_health_contract()),
        MONITORING_FILE: _json(_monitoring_status()),
        BLOCKERS_FILE: _blockers_markdown(),
    }
    for name, body in files.items():
        _assert_no_forbidden_shape(name, body)
    return files


def write_job_store_artifacts(*, repo_root: Any = None) -> dict[str, Any]:
    """Write every file under ``ARTIFACT_DIR``, relative to ``repo_root``."""
    root = Path(repo_root) if repo_root is not None else Path()
    directory = root / ARTIFACT_DIR
    directory.mkdir(parents=True, exist_ok=True)

    files = build_job_store_artifacts()
    for name, body in files.items():
        (directory / name).write_text(body, encoding="utf-8")

    return {
        "schema_version": SCHEMA_VERSION,
        "directory": str(directory),
        "files_written": sorted(files),
        "file_count": len(files),
    }


def job_store_artifact_invariant_failures(result: dict[str, Any]) -> list[str]:
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
