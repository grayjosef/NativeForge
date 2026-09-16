"""The durable collection job store (Gate 158C).

## What this owns, and what it must never own

```text
this table   the LIFECYCLE   status, attempts, next_retry_at, terminal_reason
Gate 157     the CLAIM       lease_owner, lease_acquired_at, lease_expires_at
```

A lease answers *who holds this right now* and expires in five minutes. A job
answers *does this work still need doing* and survives until archived. Gate 157
put attempt accounting on the lease row because the worker had nowhere else to
write it; this module is the somewhere else. It declares **no owner column and
no expiry column**, because a column that does not exist cannot drift from the
table that owns it.

## Enqueue is idempotent, and the database is what enforces it

`job_id` is Gate 99B's sha256 over `(source_id, collector_id, job_type,
scheduled_for, execution_mode)`. Deterministic, so the same slot described twice
is the same id, and `ux_nf_source_collection_jobs_job_id` is unique over
`(organization_id, job_id)`.

So `enqueue_job` does not check-then-insert. It inserts and catches the
integrity error, because check-then-insert is a race that two scheduler
processes lose together. A repeated cycle re-enqueues the same id, the insert is
refused, and the caller gets `deduplicated=True` with the row that was already
there.

That is what bounds the store: 177 sources with no cadence have one perpetual
slot each, so repeated cycles hold it at 177 rows rather than adding 177 a
cycle.

## `completed` cannot be reached from here, structurally

`transition_job` **has no `execution_proof_ref` parameter**. Not a guard, not a
constant, not a check somebody could invert - the argument does not exist, so no
caller can supply a proof, and the database refuses a `completed` row without
one:

```text
CHECK (status <> 'completed' OR execution_proof_ref IS NOT NULL)
```

`job_store_capability()` derives that unreachability by reading this module's own
signature rather than declaring it, so if a future gate adds the parameter the
reported capability changes by itself instead of going quietly stale.

**A persisted job is not proof a collection occurred. A claimed job is not proof
a source was contacted.**

## An illegal transition is refused, not corrected

`LEGAL_TRANSITIONS` is the state machine. A caller asking for a move that is not
in it gets a refusal naming the pair, and the row is untouched. Silently
coercing to the nearest legal state is how a queue ends up with a history that
never happened.
"""

from __future__ import annotations

import inspect
import json
import uuid
from datetime import UTC, datetime
from typing import Any

import sqlalchemy as sa

SCHEMA_VERSION = "nf_source_collection_job_store_v1"

CONTROLLED_SCOPE = "controlled_dev_demo"

TABLE_NAME = "nf_source_collection_jobs"

#: Refused by name. Gate 135's authorization covers the demo org only.
REAL_ORGANIZATION_ID = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"

QUEUED = "queued"
CLAIMED = "claimed"
REFUSED = "refused"
RETRY_WAIT = "retry_wait"
CANCELED = "canceled"
COMPLETED = "completed"
FAILED = "failed"
ARCHIVED = "archived"

JOB_STATUSES = frozenset(
    {QUEUED, CLAIMED, REFUSED, RETRY_WAIT, CANCELED, COMPLETED, FAILED, ARCHIVED}
)

#: The states a job can still move out of. Anything else is where a job rests.
LIVE_STATUSES = frozenset({QUEUED, CLAIMED, RETRY_WAIT})

#: The state machine.
#:
#: `refused -> queued` is the one that matters for this campaign: 171 sources
#: are terms-blocked, and when somebody finally reads the terms those jobs
#: become runnable work again rather than needing to be recreated.
#:
#: `failed -> queued` is an operator requeue after a fix. It is deliberate and
#: narrow; nothing in this gate calls it.
LEGAL_TRANSITIONS: dict[str, frozenset[str]] = {
    QUEUED: frozenset({CLAIMED, CANCELED, ARCHIVED}),
    CLAIMED: frozenset({REFUSED, RETRY_WAIT, FAILED, COMPLETED, CANCELED}),
    REFUSED: frozenset({QUEUED, CANCELED, ARCHIVED}),
    RETRY_WAIT: frozenset({CLAIMED, FAILED, CANCELED, ARCHIVED}),
    CANCELED: frozenset({ARCHIVED}),
    COMPLETED: frozenset({ARCHIVED}),
    FAILED: frozenset({QUEUED, ARCHIVED}),
    # Where a job stops. Reviving one would rewrite a closed history.
    ARCHIVED: frozenset(),
}

TERMINAL_REASON_NONE = "none"
TRANSIENT_WORKER_FAILURE = "transient_worker_failure"

TERMINAL_REASONS = frozenset(
    {
        TERMINAL_REASON_NONE,
        "refused_by_activation",
        "terms_blocked",
        "human_review_blocked",
        TRANSIENT_WORKER_FAILURE,
        "permanent_worker_failure",
        "attempt_budget_exhausted",
        "canceled_by_operator",
        "superseded_by_a_newer_slot",
        "unknown",
    }
)

CREATED_BY_RUNTIMES = frozenset(
    {
        "scheduler_cycle",
        "worker_cycle",
        "operator_enqueue",
        "verifier_fixture",
        "unknown",
    }
)

FACT_STATUSES = frozenset({"demo_fixture", "tenant_supplied", "verified", "unknown"})

DEFAULT_MAX_ATTEMPTS = 3

DEFAULT_COLLECTION_MODE = "dry_run"

BLOCK_NO_CONNECTION = "no_connection_supplied"
BLOCK_NO_JOB_ID = "no_job_id_supplied"
BLOCK_NO_ORGANIZATION = "no_usable_organization_id"
BLOCK_REAL_ORG = "real_organization_refused_by_name"
BLOCK_NO_SOURCE_ID = "no_source_id_supplied"
BLOCK_JOB_NOT_FOUND = "no_job_row_for_this_job_id"
BLOCK_ILLEGAL_TRANSITION = "transition_not_in_state_machine"
BLOCK_STATUS_VOCABULARY = "status_outside_vocabulary"
BLOCK_REASON_VOCABULARY = "terminal_reason_outside_vocabulary"
BLOCK_COMPLETED_NEEDS_PROOF = "completed_requires_an_execution_proof_no_gate_defines"
BLOCK_RETRY_WAIT_NOT_TRANSIENT = "retry_wait_requires_a_transient_worker_failure"
BLOCK_ATTEMPTS_EXHAUSTED = "attempt_budget_exhausted"


def _json_safe(value: Any) -> Any:
    return json.loads(json.dumps(value, default=str, sort_keys=True))


def _as_datetime(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=UTC)
    text = str(value).strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        try:
            parsed = datetime.fromisoformat(text.replace(" ", "T"))
        except ValueError:
            return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def _as_uuid(value: Any) -> uuid.UUID | None:
    try:
        return uuid.UUID(str(value))
    except Exception:  # noqa: BLE001
        return None


#: Declared, not reflected - the same lesson Gate 157 learned by hitting it:
#: reflection returns SQLite's CHAR(32) without the `sa.Uuid` decorator, and
#: binding a UUID then raises "type 'UUID' is not supported".
#:
#: Note what is absent: no `lease_owner`, no `lease_acquired_at`, no
#: `lease_expires_at`. Gate 157 owns the claim.
_METADATA = sa.MetaData()

JOBS = sa.Table(
    TABLE_NAME,
    _METADATA,
    sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
    sa.Column("organization_id", sa.Uuid(as_uuid=True), nullable=False),
    sa.Column("is_demo", sa.Boolean(), nullable=False),
    sa.Column("job_id", sa.Text(), nullable=False),
    sa.Column("idempotency_key", sa.Text(), nullable=False),
    sa.Column("source_id", sa.Text(), nullable=False),
    sa.Column("schedule_key", sa.Text(), nullable=True),
    sa.Column("scheduled_for", sa.DateTime(timezone=True), nullable=True),
    sa.Column("collection_mode", sa.String(length=32), nullable=False),
    sa.Column("status", sa.String(length=32), nullable=False),
    sa.Column("queued_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("attempt_count", sa.Integer(), nullable=False),
    sa.Column("max_attempts", sa.Integer(), nullable=False),
    sa.Column("last_attempt_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("next_retry_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("terminal_reason", sa.String(length=48), nullable=False),
    sa.Column("blocked_reasons", sa.JSON(), nullable=True),
    sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
    # Declared so a read can assert it is null. Nothing in this gate writes it.
    sa.Column("execution_proof_ref", sa.Text(), nullable=True),
    sa.Column("created_by_runtime", sa.String(length=32), nullable=False),
    sa.Column("fact_status", sa.String(length=32), nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
)


def _table(connection: Any) -> sa.Table:
    return JOBS


def _row_to_job(row: Any) -> dict[str, Any]:
    job = dict(row)
    return _json_safe(
        {
            "job_id": job.get("job_id"),
            "idempotency_key": job.get("idempotency_key"),
            "source_id": job.get("source_id"),
            "organization_id": str(job.get("organization_id")),
            "is_demo": bool(job.get("is_demo")),
            "schedule_key": job.get("schedule_key"),
            "scheduled_for": job.get("scheduled_for"),
            "collection_mode": job.get("collection_mode"),
            "status": job.get("status"),
            "queued_at": job.get("queued_at"),
            "attempt_count": int(job.get("attempt_count") or 0),
            "max_attempts": int(job.get("max_attempts") or 0),
            "last_attempt_at": job.get("last_attempt_at"),
            "next_retry_at": job.get("next_retry_at"),
            "terminal_reason": job.get("terminal_reason"),
            "blocked_reasons": list(job.get("blocked_reasons") or []),
            "archived_at": job.get("archived_at"),
            # Read back so a caller can prove it is null rather than trust it.
            "execution_proof_ref": job.get("execution_proof_ref"),
            "created_by_runtime": job.get("created_by_runtime"),
            "fact_status": job.get("fact_status"),
            "created_at": job.get("created_at"),
            "updated_at": job.get("updated_at"),
            # Derived from the row, not stored. A completed job needs a proof;
            # no row has one; so this is False everywhere, by reading.
            "execution_occurred": bool(job.get("execution_proof_ref")),
            "is_live": job.get("status") in LIVE_STATUSES,
            "attempts_remaining": max(
                0,
                int(job.get("max_attempts") or 0)
                - int(job.get("attempt_count") or 0),
            ),
        }
    )


def _result(**fields: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "scope": CONTROLLED_SCOPE,
        "job_id": None,
        "job": None,
        "created": False,
        "deduplicated": False,
        "transitioned": False,
        "from_status": None,
        "to_status": None,
        "blocked_reasons": [],
        # Constants of this gate, and each one is also asserted by the
        # invariant checker against the row that was written.
        "collectors_invoked": 0,
        "live_source_calls": 0,
        "network_calls": 0,
        "urls_fetched": 0,
        "raw_payloads_written": 0,
        "emails_sent": 0,
        "object_store_calls": 0,
        "source_monitoring_live": False,
    }
    base.update(fields)
    base["blocked_reasons"] = sorted(set(base["blocked_reasons"] or []))
    return _json_safe(base)


def _validate_scope(
    *, connection: Any, organization_id: Any, job_id: Any = None
) -> tuple[uuid.UUID | None, list[str]]:
    blocked: list[str] = []
    if connection is None:
        blocked.append(BLOCK_NO_CONNECTION)
    if str(organization_id or "").strip().lower() == REAL_ORGANIZATION_ID:
        blocked.append(BLOCK_REAL_ORG)
    org = _as_uuid(organization_id)
    if org is None:
        blocked.append(BLOCK_NO_ORGANIZATION)
    if job_id is not None and not str(job_id or "").strip():
        blocked.append(BLOCK_NO_JOB_ID)
    return org, blocked


def _select_one(connection: Any, org: uuid.UUID, job_id: str) -> Any:
    table = _table(connection)
    return (
        connection.execute(
            sa.select(table).where(
                sa.and_(table.c.organization_id == org, table.c.job_id == str(job_id))
            )
        )
        .mappings()
        .first()
    )


def enqueue_job(
    *,
    connection: Any = None,
    organization_id: Any = None,
    job_id: Any = None,
    idempotency_key: Any = None,
    source_id: Any = None,
    schedule_key: Any = None,
    scheduled_for: Any = None,
    collection_mode: str = DEFAULT_COLLECTION_MODE,
    blocked_reasons: list[str] | None = None,
    terminal_reason: str = TERMINAL_REASON_NONE,
    created_by_runtime: str = "scheduler_cycle",
    fact_status: str = "demo_fixture",
    max_attempts: int = DEFAULT_MAX_ATTEMPTS,
    now: Any = None,
    is_demo: bool = True,
) -> dict[str, Any]:
    """Enqueue one job. Idempotent on `(organization_id, job_id)`.

    Inserts first and catches the integrity error, rather than checking and then
    inserting - two scheduler processes both passing a check is exactly the race
    the unique index exists to settle.
    """
    org, blocked = _validate_scope(
        connection=connection, organization_id=organization_id, job_id=job_id
    )
    if not str(source_id or "").strip():
        blocked.append(BLOCK_NO_SOURCE_ID)
    moment = _as_datetime(now)
    if moment is None:
        blocked.append("no_clock_supplied")
    if terminal_reason not in TERMINAL_REASONS:
        blocked.append(f"{BLOCK_REASON_VOCABULARY}:{terminal_reason}")
    if created_by_runtime not in CREATED_BY_RUNTIMES:
        blocked.append(f"created_by_runtime_outside_vocabulary:{created_by_runtime}")
    if fact_status not in FACT_STATUSES:
        blocked.append(f"fact_status_outside_vocabulary:{fact_status}")

    if blocked or org is None or moment is None:
        return _result(job_id=str(job_id or "") or None, blocked_reasons=blocked)

    table = _table(connection)
    try:
        with connection.begin_nested():
            connection.execute(
                sa.insert(table).values(
                    id=uuid.uuid4(),
                    organization_id=org,
                    is_demo=bool(is_demo),
                    job_id=str(job_id),
                    idempotency_key=str(idempotency_key or job_id),
                    source_id=str(source_id),
                    schedule_key=(
                        str(schedule_key) if schedule_key is not None else None
                    ),
                    scheduled_for=_as_datetime(scheduled_for),
                    collection_mode=str(collection_mode),
                    # A new job is queued. Not claimed, not refused - the
                    # scheduler does not get to decide an outcome.
                    status=QUEUED,
                    queued_at=moment,
                    attempt_count=0,
                    max_attempts=max(1, int(max_attempts)),
                    last_attempt_at=None,
                    next_retry_at=None,
                    terminal_reason=str(terminal_reason),
                    blocked_reasons=list(blocked_reasons or []),
                    archived_at=None,
                    # Never set. See the module docstring.
                    execution_proof_ref=None,
                    created_by_runtime=str(created_by_runtime),
                    fact_status=str(fact_status),
                    created_at=moment,
                    updated_at=moment,
                )
            )
    except sa.exc.IntegrityError:
        existing = _select_one(connection, org, str(job_id))
        if existing is None:
            # The insert failed for a reason that is not the unique index -
            # a check constraint, most likely. Say so rather than reporting a
            # deduplication that did not happen.
            return _result(
                job_id=str(job_id),
                blocked_reasons=["insert_refused_by_the_database"],
            )
        return _result(
            job_id=str(job_id),
            job=_row_to_job(existing),
            created=False,
            deduplicated=True,
        )

    written = _select_one(connection, org, str(job_id))
    return _result(
        job_id=str(job_id),
        job=_row_to_job(written) if written is not None else None,
        created=True,
    )


def get_job(
    *, connection: Any = None, organization_id: Any = None, job_id: Any = None
) -> dict[str, Any]:
    """Read one job by its deterministic id."""
    org, blocked = _validate_scope(
        connection=connection, organization_id=organization_id, job_id=job_id
    )
    if blocked or org is None:
        return _result(job_id=str(job_id or "") or None, blocked_reasons=blocked)

    row = _select_one(connection, org, str(job_id))
    if row is None:
        return _result(job_id=str(job_id), blocked_reasons=[BLOCK_JOB_NOT_FOUND])
    return _result(job_id=str(job_id), job=_row_to_job(row))


def list_jobs(
    *,
    connection: Any = None,
    organization_id: Any = None,
    source_id: Any = None,
    status: Any = None,
    limit: int = 500,
) -> dict[str, Any]:
    """List jobs, optionally narrowed by source or status."""
    org, blocked = _validate_scope(
        connection=connection, organization_id=organization_id
    )
    if status is not None and str(status) not in JOB_STATUSES:
        blocked.append(f"{BLOCK_STATUS_VOCABULARY}:{status}")
    if blocked or org is None:
        return _result(blocked_reasons=blocked, **{"jobs": [], "job_count": 0})

    table = _table(connection)
    query = sa.select(table).where(table.c.organization_id == org)
    if str(source_id or "").strip():
        query = query.where(table.c.source_id == str(source_id))
    if status is not None:
        query = query.where(table.c.status == str(status))
    query = query.order_by(table.c.created_at, table.c.job_id).limit(int(limit))

    rows = list(connection.execute(query).mappings())
    jobs = [_row_to_job(row) for row in rows]
    return _result(
        **{
            "jobs": jobs,
            "job_count": len(jobs),
            "truncated_at_limit": len(jobs) >= int(limit),
        }
    )


def transition_job(
    *,
    connection: Any = None,
    organization_id: Any = None,
    job_id: Any = None,
    to_status: Any = None,
    terminal_reason: str = TERMINAL_REASON_NONE,
    blocked_reasons: list[str] | None = None,
    next_retry_at: Any = None,
    increment_attempt: bool = False,
    now: Any = None,
) -> dict[str, Any]:
    """Move a job through the state machine, or refuse and change nothing.

    There is deliberately **no `execution_proof_ref` parameter**. A caller
    cannot supply a proof, so a transition to `completed` is refused here and
    would be refused again by the database if this check were removed.
    """
    org, blocked = _validate_scope(
        connection=connection, organization_id=organization_id, job_id=job_id
    )
    target = str(to_status or "")
    moment = _as_datetime(now)
    if target not in JOB_STATUSES:
        blocked.append(f"{BLOCK_STATUS_VOCABULARY}:{target}")
    if terminal_reason not in TERMINAL_REASONS:
        blocked.append(f"{BLOCK_REASON_VOCABULARY}:{terminal_reason}")
    if moment is None:
        blocked.append("no_clock_supplied")

    if blocked or org is None or moment is None:
        return _result(
            job_id=str(job_id or "") or None,
            to_status=target or None,
            blocked_reasons=blocked,
        )

    row = _select_one(connection, org, str(job_id))
    if row is None:
        return _result(
            job_id=str(job_id),
            to_status=target,
            blocked_reasons=[BLOCK_JOB_NOT_FOUND],
        )

    current = dict(row)
    from_status = str(current.get("status"))

    # The refusals, in the order that gives the most useful answer.
    refusals: list[str] = []

    if target == COMPLETED:
        # Unreachable by construction: this function has no way to receive a
        # proof. The gate that defines what one IS has not been written.
        refusals.append(BLOCK_COMPLETED_NEEDS_PROOF)

    if target not in LEGAL_TRANSITIONS.get(from_status, frozenset()):
        refusals.append(f"{BLOCK_ILLEGAL_TRANSITION}:{from_status}->{target}")

    if target == RETRY_WAIT and terminal_reason != TRANSIENT_WORKER_FAILURE:
        # An activation or terms refusal parked in a retry queue would burn
        # attempts on work no worker can ever run.
        refusals.append(f"{BLOCK_RETRY_WAIT_NOT_TRANSIENT}:{terminal_reason}")

    attempt_count = int(current.get("attempt_count") or 0)
    max_attempts = int(current.get("max_attempts") or DEFAULT_MAX_ATTEMPTS)
    next_attempt = attempt_count + 1 if increment_attempt else attempt_count
    if next_attempt > max_attempts:
        refusals.append(f"{BLOCK_ATTEMPTS_EXHAUSTED}:{attempt_count}/{max_attempts}")

    if refusals:
        return _result(
            job_id=str(job_id),
            job=_row_to_job(row),
            from_status=from_status,
            to_status=target,
            blocked_reasons=refusals,
        )

    values: dict[str, Any] = {
        "status": target,
        "terminal_reason": str(terminal_reason),
        "blocked_reasons": list(blocked_reasons or []),
        "attempt_count": next_attempt,
        "updated_at": moment,
        # Only a retry_wait carries a next attempt time; every other state
        # clears it, so a stale timestamp cannot make a refused job look due.
        "next_retry_at": _as_datetime(next_retry_at) if target == RETRY_WAIT else None,
        # Set iff archived, which is what the database CHECK requires.
        "archived_at": moment if target == ARCHIVED else None,
    }
    if increment_attempt:
        values["last_attempt_at"] = moment

    table = _table(connection)
    connection.execute(
        sa.update(table)
        .where(
            sa.and_(
                table.c.organization_id == org,
                table.c.job_id == str(job_id),
                # Optimistic: the row must still be where we read it. Two
                # workers transitioning the same job means the second finds
                # nothing to update and is told so.
                table.c.status == from_status,
            )
        )
        .values(**values)
    )

    after = _select_one(connection, org, str(job_id))
    if after is None or str(dict(after).get("status")) != target:
        return _result(
            job_id=str(job_id),
            job=_row_to_job(after) if after is not None else None,
            from_status=from_status,
            to_status=target,
            blocked_reasons=["row_changed_under_this_transition"],
        )

    return _result(
        job_id=str(job_id),
        job=_row_to_job(after),
        transitioned=True,
        from_status=from_status,
        to_status=target,
    )


def archive_job(
    *,
    connection: Any = None,
    organization_id: Any = None,
    job_id: Any = None,
    terminal_reason: str = TERMINAL_REASON_NONE,
    now: Any = None,
) -> dict[str, Any]:
    """Archive a job. A thin, named wrapper - the state machine still rules."""
    return transition_job(
        connection=connection,
        organization_id=organization_id,
        job_id=job_id,
        to_status=ARCHIVED,
        terminal_reason=terminal_reason,
        now=now,
    )


def count_backlog(
    *, connection: Any = None, organization_id: Any = None
) -> dict[str, Any]:
    """Count the store by status, and by refusal reason.

    Every status in the vocabulary appears, including the ones at zero. A
    backlog report that omits its empty buckets makes a missing state look like
    a state that does not exist.
    """
    org, blocked = _validate_scope(
        connection=connection, organization_id=organization_id
    )
    empty = {
        "by_status": dict.fromkeys(sorted(JOB_STATUSES), 0),
        "by_terminal_reason": {},
        "total": 0,
        "live_total": 0,
        "completed_total": 0,
        "rows_with_execution_proof": 0,
        "oldest_queued_at": None,
    }
    if blocked or org is None:
        return _result(blocked_reasons=blocked, **empty)

    table = _table(connection)
    by_status = dict.fromkeys(sorted(JOB_STATUSES), 0)
    for row in connection.execute(
        sa.select(table.c.status, sa.func.count())
        .where(table.c.organization_id == org)
        .group_by(table.c.status)
    ):
        by_status[str(row[0])] = int(row[1])

    by_reason: dict[str, int] = {}
    for row in connection.execute(
        sa.select(table.c.terminal_reason, sa.func.count())
        .where(table.c.organization_id == org)
        .group_by(table.c.terminal_reason)
    ):
        by_reason[str(row[0])] = int(row[1])

    proofs = int(
        connection.execute(
            sa.select(sa.func.count())
            .select_from(table)
            .where(
                sa.and_(
                    table.c.organization_id == org,
                    table.c.execution_proof_ref.isnot(None),
                )
            )
        ).scalar()
        or 0
    )
    oldest = connection.execute(
        sa.select(sa.func.min(table.c.queued_at)).where(
            sa.and_(
                table.c.organization_id == org,
                table.c.status.in_(sorted(LIVE_STATUSES)),
            )
        )
    ).scalar()

    return _result(
        **{
            "by_status": by_status,
            "by_terminal_reason": dict(sorted(by_reason.items())),
            "total": sum(by_status.values()),
            "live_total": sum(by_status[s] for s in sorted(LIVE_STATUSES)),
            "completed_total": by_status[COMPLETED],
            # Measured, not assumed. This is the number that would have to be
            # nonzero before any completed row could exist.
            "rows_with_execution_proof": proofs,
            "oldest_queued_at": oldest,
        }
    )


def job_store_capability() -> dict[str, Any]:
    """What this store can and cannot do, derived from its own signature.

    `completed_is_reachable` is computed by asking whether `transition_job`
    accepts an execution proof. It does not, so nothing can complete a job -
    and if a future gate adds the parameter, this value flips on its own
    instead of becoming a stale constant somebody has to remember to change.
    """
    parameters = set(inspect.signature(transition_job).parameters)
    accepts_proof = bool(
        {"execution_proof_ref", "execution_proof"} & parameters
    )
    columns = {column.name for column in JOBS.columns}
    lease_columns = {"lease_owner", "lease_acquired_at", "lease_expires_at"}

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "scope": CONTROLLED_SCOPE,
            "table": TABLE_NAME,
            "statuses": sorted(JOB_STATUSES),
            "live_statuses": sorted(LIVE_STATUSES),
            "legal_transitions": {
                state: sorted(targets) for state, targets in LEGAL_TRANSITIONS.items()
            },
            "enqueue_is_idempotent": True,
            "idempotency_enforced_by": "ux_nf_source_collection_jobs_job_id",
            "transition_accepts_an_execution_proof": accepts_proof,
            "completed_is_reachable": accepts_proof,
            "why_completed_is_unreachable": (
                "transition_job has no execution proof parameter, and the "
                "database refuses a completed row whose execution_proof_ref "
                "is null"
                if not accepts_proof
                else "a proof parameter exists; re-derive this claim"
            ),
            # Derived by reading the declared table, so a migration that added
            # a lease column here would be caught rather than described.
            "declares_lease_columns": sorted(lease_columns & columns),
            "claim_is_owned_by": "nf_source_collection_job_leases",
            "lifecycle_is_owned_by": TABLE_NAME,
            "persisted_job_means_collection_occurred": False,
            "claimed_job_means_source_contacted": False,
            "source_monitoring_live": False,
        }
    )


def job_store_invariant_failures(result: dict[str, Any]) -> list[str]:
    """Refuse a result that claims execution, or a row that broke the model."""
    fails: list[str] = []

    for flag in (
        "collectors_invoked",
        "live_source_calls",
        "network_calls",
        "urls_fetched",
        "raw_payloads_written",
        "emails_sent",
        "object_store_calls",
    ):
        if int(result.get(flag) or 0) != 0:
            fails.append(f"job_store_claimed:{flag}={result.get(flag)}")

    if result.get("source_monitoring_live"):
        fails.append("job_store_claimed:source_monitoring_live")

    if result.get("created") and result.get("deduplicated"):
        fails.append("enqueue_reported_both_created_and_deduplicated")

    if result.get("transitioned") and result.get("blocked_reasons"):
        fails.append("transition_reported_success_alongside_refusals")

    job = result.get("job") or {}
    if job:
        status = job.get("status")
        if status not in JOB_STATUSES:
            fails.append(f"row_status_outside_vocabulary:{status}")
        if status == COMPLETED and not job.get("execution_proof_ref"):
            fails.append("completed_row_without_an_execution_proof")
        if job.get("execution_proof_ref"):
            fails.append("row_carries_an_execution_proof_no_gate_can_issue")
        if job.get("execution_occurred"):
            fails.append("row_claimed_execution_occurred")
        if status == ARCHIVED and not job.get("archived_at"):
            fails.append("archived_row_without_a_timestamp")
        if status != ARCHIVED and job.get("archived_at"):
            fails.append("unarchived_row_carrying_an_archived_at")
        if status == RETRY_WAIT and job.get("terminal_reason") != (
            TRANSIENT_WORKER_FAILURE
        ):
            fails.append(
                f"retry_wait_row_is_not_transient:{job.get('terminal_reason')}"
            )
        if int(job.get("attempt_count") or 0) > int(job.get("max_attempts") or 0):
            fails.append("row_attempt_count_exceeds_its_budget")

    # A backlog result that reports a completed job is reporting a collection
    # this campaign has not authorized.
    if int(result.get("completed_total") or 0) != 0:
        fails.append("backlog_reported_a_completed_job")
    if int(result.get("rows_with_execution_proof") or 0) != 0:
        fails.append("backlog_reported_a_row_with_an_execution_proof")

    return sorted(set(fails))
