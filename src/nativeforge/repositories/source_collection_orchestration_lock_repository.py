"""Single-active-cycle ownership (Gate 159E).

## Orchestration ownership, not a second job lease

```text
nf_source_collection_job_leases   per JOB    who is working this one piece
nf_source_orchestration_cycles    per CYCLE  who is running the loop
```

One cycle covers every source in a pass and produces many jobs. This module
declares none of Gate 157's lease columns and Gate 157 declares none of these;
the two answer different questions with different lifetimes.

## Acquisition is atomic because the index says so

`cycle_id` is deterministic over `(orchestration_version, cadence, slot_index)`,
and `ux_nf_source_orchestration_cycles_cycle_id` is unique over
`(organization_id, cycle_id)`. So `acquire_cycle` **inserts and catches the
integrity error** rather than checking first: two processes racing for one slot
both attempt the same id and one insert fails. A check-then-insert would have a
window between the two halves that both processes could pass through.

That is the third use of this primitive in the block - Gate 157 for the job
claim, Gate 158 for enqueue idempotency, Gate 159 for cycle ownership - and it
is deliberate. SQLite has no advisory lock, so a unique index is the portable
atomic operation available (doc 827 measured zero advisory-lock primitives in
the repository).

## Expiry is what stops one crash blocking the loop forever

A crashed owner cannot release. If ownership had no expiry, the slot it held
would be unownable until somebody deleted the row by hand, and the migration
refuses an `acquired` row without an `expires_at` for exactly that reason.

A non-expired owner cannot be stolen. An expired one can, and the reclaim
increments `reclaim_count` so "this keeps happening" is a measurable fact rather
than an impression.

## Staleness is derived, never stored

A row is stale when `expires_at` has passed and nothing released it. That is
computed against an injected clock on read. Storing a `stale` status would
require a sweeper process to keep it true, and a status that needs a sweeper is
wrong between sweeps.
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import sqlalchemy as sa

SCHEMA_VERSION = "nf_source_orchestration_cycle_lock_v1"

CONTROLLED_SCOPE = "controlled_dev_demo"

TABLE_NAME = "nf_source_orchestration_cycles"

#: Refused by name. Gate 135's authorization covers the demo org only.
REAL_ORGANIZATION_ID = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"

ACQUIRED = "acquired"
RELEASED = "released"
EXPIRED = "expired"
ABANDONED = "abandoned"
UNKNOWN = "unknown"

CYCLE_STATUSES = frozenset({ACQUIRED, RELEASED, EXPIRED, ABANDONED, UNKNOWN})

OUTCOME_NONE = "none"
OUTCOME_COMPLETED = "completed_normally"
OUTCOME_RELEASED_EARLY = "released_early"
OUTCOME_RECLAIMED = "reclaimed_from_an_expired_owner"
OUTCOME_DUPLICATE = "refused_duplicate_slot"
OUTCOME_NOT_DUE = "trigger_not_due"
OUTCOME_OPERATOR = "operator_stopped"

CYCLE_OUTCOMES = frozenset(
    {
        OUTCOME_NONE,
        OUTCOME_COMPLETED,
        OUTCOME_RELEASED_EARLY,
        OUTCOME_RECLAIMED,
        OUTCOME_DUPLICATE,
        OUTCOME_NOT_DUE,
        OUTCOME_OPERATOR,
        UNKNOWN,
    }
)

FACT_STATUSES = frozenset({"demo_fixture", "tenant_supplied", "verified", "unknown"})

#: Long enough for a cycle over 177 refused sources, short enough that a crashed
#: owner does not hold the slot for a whole cadence window.
DEFAULT_LEASE_SECONDS = 600

BLOCK_NO_CONNECTION = "no_connection_supplied"
BLOCK_NO_ORGANIZATION = "no_usable_organization_id"
BLOCK_REAL_ORG = "real_organization_refused_by_name"
BLOCK_NO_CYCLE_ID = "no_cycle_id_supplied"
BLOCK_NO_OWNER = "no_owner_id_supplied"
BLOCK_NO_CLOCK = "no_clock_supplied"
BLOCK_ALREADY_OWNED = "cycle_is_already_owned_by_another_process"
BLOCK_NOT_EXPIRED = "ownership_has_not_expired_and_cannot_be_stolen"
BLOCK_ALREADY_SERVED = "this_slot_has_already_been_served"
BLOCK_NOT_FOUND = "no_cycle_row_for_this_cycle_id"
BLOCK_NOT_THE_OWNER = "caller_does_not_own_this_cycle"


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


#: Declared, not reflected - Gate 157 lost the `sa.Uuid` decorator to reflection
#: and got "type 'UUID' is not supported" when binding a UUID.
#:
#: Note what is absent: no lease_owner, no lease_acquired_at, no
#: lease_expires_at. Gate 157 owns the job claim.
_METADATA = sa.MetaData()

CYCLES = sa.Table(
    TABLE_NAME,
    _METADATA,
    sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
    sa.Column("organization_id", sa.Uuid(as_uuid=True), nullable=False),
    sa.Column("is_demo", sa.Boolean(), nullable=False),
    sa.Column("cycle_id", sa.Text(), nullable=False),
    sa.Column("orchestration_version", sa.String(length=32), nullable=False),
    sa.Column("cadence", sa.String(length=32), nullable=False),
    sa.Column("slot_index", sa.BigInteger(), nullable=False),
    sa.Column("slot_key", sa.Text(), nullable=True),
    sa.Column("owner_id", sa.Text(), nullable=True),
    sa.Column("acquired_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("released_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("cycle_status", sa.String(length=32), nullable=False),
    sa.Column("cycle_outcome", sa.String(length=48), nullable=False),
    sa.Column("reclaim_count", sa.Integer(), nullable=False),
    sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("sources_seen", sa.Integer(), nullable=False),
    sa.Column("jobs_created", sa.Integer(), nullable=False),
    sa.Column("jobs_reused", sa.Integer(), nullable=False),
    sa.Column("jobs_blocked", sa.Integer(), nullable=False),
    sa.Column("jobs_claimed", sa.Integer(), nullable=False),
    sa.Column("jobs_refused", sa.Integer(), nullable=False),
    sa.Column("missed_windows_recovered", sa.Integer(), nullable=False),
    sa.Column("duplicate_triggers_suppressed", sa.Integer(), nullable=False),
    # Declared so a read can assert them. The database refuses any other value.
    sa.Column("jobs_completed", sa.Integer(), nullable=False),
    sa.Column("collectors_invoked", sa.Integer(), nullable=False),
    sa.Column("live_source_calls", sa.Integer(), nullable=False),
    sa.Column("fact_status", sa.String(length=32), nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
)


def _row_to_cycle(row: Any, *, now: Any = None) -> dict[str, Any]:
    cycle = dict(row)
    moment = _as_datetime(now)
    expires = _as_datetime(cycle.get("expires_at"))
    status = str(cycle.get("cycle_status") or "")

    # Derived on read, against the supplied clock. A stored `stale` status
    # would need a sweeper to stay true, and would be wrong between sweeps.
    is_expired = bool(
        status == ACQUIRED and moment is not None and expires is not None
        and expires <= moment
    )

    return _json_safe(
        {
            "cycle_id": cycle.get("cycle_id"),
            "organization_id": str(cycle.get("organization_id")),
            "is_demo": bool(cycle.get("is_demo")),
            "orchestration_version": cycle.get("orchestration_version"),
            "cadence": cycle.get("cadence"),
            "slot_index": cycle.get("slot_index"),
            "slot_key": cycle.get("slot_key"),
            "owner_id": cycle.get("owner_id"),
            "acquired_at": cycle.get("acquired_at"),
            "expires_at": cycle.get("expires_at"),
            "released_at": cycle.get("released_at"),
            "cycle_status": status,
            "cycle_outcome": cycle.get("cycle_outcome"),
            "reclaim_count": int(cycle.get("reclaim_count") or 0),
            "started_at": cycle.get("started_at"),
            "completed_at": cycle.get("completed_at"),
            "sources_seen": int(cycle.get("sources_seen") or 0),
            "jobs_created": int(cycle.get("jobs_created") or 0),
            "jobs_reused": int(cycle.get("jobs_reused") or 0),
            "jobs_blocked": int(cycle.get("jobs_blocked") or 0),
            "jobs_claimed": int(cycle.get("jobs_claimed") or 0),
            "jobs_refused": int(cycle.get("jobs_refused") or 0),
            "missed_windows_recovered": int(
                cycle.get("missed_windows_recovered") or 0
            ),
            "duplicate_triggers_suppressed": int(
                cycle.get("duplicate_triggers_suppressed") or 0
            ),
            # Read back so a caller can prove they are zero rather than trust
            # a Python constant.
            "jobs_completed": int(cycle.get("jobs_completed") or 0),
            "collectors_invoked": int(cycle.get("collectors_invoked") or 0),
            "live_source_calls": int(cycle.get("live_source_calls") or 0),
            "fact_status": cycle.get("fact_status"),
            "created_at": cycle.get("created_at"),
            "updated_at": cycle.get("updated_at"),
            # ---- derived ------------------------------------------------
            "is_owned": status == ACQUIRED and not is_expired,
            "ownership_is_expired": is_expired,
            "is_finished": status in (RELEASED, EXPIRED, ABANDONED),
        }
    )


def _result(**fields: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "scope": CONTROLLED_SCOPE,
        "cycle_id": None,
        "cycle": None,
        "acquired": False,
        "reclaimed": False,
        "released": False,
        "duplicate_suppressed": False,
        "blocked_reasons": [],
        # Constants of this gate, asserted by the invariant checker against the
        # row that was written.
        "collectors_invoked": 0,
        "live_source_calls": 0,
        "network_calls": 0,
        "jobs_completed": 0,
        "source_monitoring_live": False,
    }
    base.update(fields)
    base["blocked_reasons"] = sorted(set(base["blocked_reasons"] or []))
    return _json_safe(base)


def _validate(
    *, connection: Any, organization_id: Any, cycle_id: Any = None, owner_id: Any = None
) -> tuple[uuid.UUID | None, list[str]]:
    blocked: list[str] = []
    if connection is None:
        blocked.append(BLOCK_NO_CONNECTION)
    if str(organization_id or "").strip().lower() == REAL_ORGANIZATION_ID:
        blocked.append(BLOCK_REAL_ORG)
    org = _as_uuid(organization_id)
    if org is None:
        blocked.append(BLOCK_NO_ORGANIZATION)
    if cycle_id is not None and not str(cycle_id or "").strip():
        blocked.append(BLOCK_NO_CYCLE_ID)
    if owner_id is not None and not str(owner_id or "").strip():
        blocked.append(BLOCK_NO_OWNER)
    return org, blocked


def _select_one(connection: Any, org: uuid.UUID, cycle_id: str) -> Any:
    return (
        connection.execute(
            sa.select(CYCLES).where(
                sa.and_(
                    CYCLES.c.organization_id == org,
                    CYCLES.c.cycle_id == str(cycle_id),
                )
            )
        )
        .mappings()
        .first()
    )


def acquire_cycle(
    *,
    connection: Any = None,
    organization_id: Any = None,
    cycle_id: Any = None,
    owner_id: Any = None,
    cadence: Any = None,
    slot_index: Any = None,
    slot_key: Any = None,
    orchestration_version: Any = None,
    now: Any = None,
    lease_seconds: int = DEFAULT_LEASE_SECONDS,
    allow_reclaim: bool = True,
    is_demo: bool = True,
    fact_status: str = "demo_fixture",
) -> dict[str, Any]:
    """Take ownership of one orchestration slot, or refuse and say why.

    Atomic on the unique index, not on a check in front of it.
    """
    org, blocked = _validate(
        connection=connection,
        organization_id=organization_id,
        cycle_id=cycle_id,
        owner_id=owner_id,
    )
    moment = _as_datetime(now)
    if moment is None:
        blocked.append(BLOCK_NO_CLOCK)
    if slot_index is None:
        blocked.append("no_slot_index_supplied")
    if fact_status not in FACT_STATUSES:
        blocked.append(f"fact_status_outside_vocabulary:{fact_status}")

    if blocked or org is None or moment is None:
        return _result(
            cycle_id=str(cycle_id or "") or None, blocked_reasons=blocked
        )

    expires = moment + timedelta(seconds=int(lease_seconds))

    try:
        with connection.begin_nested():
            connection.execute(
                sa.insert(CYCLES).values(
                    id=uuid.uuid4(),
                    organization_id=org,
                    is_demo=bool(is_demo),
                    cycle_id=str(cycle_id),
                    orchestration_version=str(orchestration_version or "unknown"),
                    cadence=str(cadence or "hourly"),
                    slot_index=int(slot_index),
                    slot_key=None if slot_key is None else str(slot_key),
                    owner_id=str(owner_id),
                    acquired_at=moment,
                    expires_at=expires,
                    released_at=None,
                    cycle_status=ACQUIRED,
                    cycle_outcome=OUTCOME_NONE,
                    reclaim_count=0,
                    started_at=moment,
                    completed_at=None,
                    sources_seen=0,
                    jobs_created=0,
                    jobs_reused=0,
                    jobs_blocked=0,
                    jobs_claimed=0,
                    jobs_refused=0,
                    missed_windows_recovered=0,
                    duplicate_triggers_suppressed=0,
                    # Never set to anything else. The database refuses it.
                    jobs_completed=0,
                    collectors_invoked=0,
                    live_source_calls=0,
                    fact_status=str(fact_status),
                    created_at=moment,
                    updated_at=moment,
                )
            )
    except sa.exc.IntegrityError:
        # The slot already has a row. Whether this caller may take it over
        # depends on what that row says, not on having lost the race.
        existing = _select_one(connection, org, str(cycle_id))
        if existing is None:
            return _result(
                cycle_id=str(cycle_id),
                blocked_reasons=["insert_refused_by_the_database"],
            )
        return _reclaim_or_refuse(
            connection=connection,
            org=org,
            existing=existing,
            cycle_id=str(cycle_id),
            owner_id=str(owner_id),
            moment=moment,
            expires=expires,
            allow_reclaim=allow_reclaim,
        )

    written = _select_one(connection, org, str(cycle_id))
    return _result(
        cycle_id=str(cycle_id),
        cycle=None if written is None else _row_to_cycle(written, now=moment),
        acquired=True,
    )


def _reclaim_or_refuse(
    *,
    connection: Any,
    org: uuid.UUID,
    existing: Any,
    cycle_id: str,
    owner_id: str,
    moment: datetime,
    expires: datetime,
    allow_reclaim: bool,
) -> dict[str, Any]:
    """The slot exists. Decide whether this caller may take it."""
    current = dict(existing)
    status = str(current.get("cycle_status") or "")
    current_expiry = _as_datetime(current.get("expires_at"))

    # A finished slot has been served. This is duplicate suppression: the
    # second trigger attempt for one slot is refused by name, not by silence.
    if status in (RELEASED, EXPIRED, ABANDONED):
        return _result(
            cycle_id=cycle_id,
            cycle=_row_to_cycle(existing, now=moment),
            duplicate_suppressed=True,
            blocked_reasons=[BLOCK_ALREADY_SERVED],
        )

    # Still owned, and the owner has not expired. Cannot be stolen.
    if status == ACQUIRED and (
        current_expiry is None or current_expiry > moment
    ):
        return _result(
            cycle_id=cycle_id,
            cycle=_row_to_cycle(existing, now=moment),
            duplicate_suppressed=True,
            blocked_reasons=[BLOCK_ALREADY_OWNED, BLOCK_NOT_EXPIRED],
        )

    if not allow_reclaim:
        return _result(
            cycle_id=cycle_id,
            cycle=_row_to_cycle(existing, now=moment),
            duplicate_suppressed=True,
            blocked_reasons=[BLOCK_ALREADY_OWNED],
        )

    # Expired. Reclaimable, and the reclaim is counted so "this keeps
    # happening" is measurable rather than an impression.
    connection.execute(
        sa.update(CYCLES)
        .where(
            sa.and_(
                CYCLES.c.organization_id == org,
                CYCLES.c.cycle_id == cycle_id,
                # Optimistic: the row must still be the expired one we read.
                CYCLES.c.cycle_status == ACQUIRED,
                CYCLES.c.owner_id == current.get("owner_id"),
            )
        )
        .values(
            owner_id=owner_id,
            acquired_at=moment,
            expires_at=expires,
            released_at=None,
            cycle_status=ACQUIRED,
            cycle_outcome=OUTCOME_RECLAIMED,
            reclaim_count=int(current.get("reclaim_count") or 0) + 1,
            started_at=moment,
            updated_at=moment,
        )
    )
    after = _select_one(connection, org, cycle_id)
    if after is None or str(dict(after).get("owner_id")) != owner_id:
        return _result(
            cycle_id=cycle_id,
            cycle=None if after is None else _row_to_cycle(after, now=moment),
            blocked_reasons=["row_changed_under_this_reclaim"],
        )
    return _result(
        cycle_id=cycle_id,
        cycle=_row_to_cycle(after, now=moment),
        acquired=True,
        reclaimed=True,
    )


def release_cycle(
    *,
    connection: Any = None,
    organization_id: Any = None,
    cycle_id: Any = None,
    owner_id: Any = None,
    now: Any = None,
    outcome: str = OUTCOME_COMPLETED,
    counters: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Finish a cycle and record what it did. Refuses a caller who does not own it."""
    org, blocked = _validate(
        connection=connection,
        organization_id=organization_id,
        cycle_id=cycle_id,
        owner_id=owner_id,
    )
    moment = _as_datetime(now)
    if moment is None:
        blocked.append(BLOCK_NO_CLOCK)
    if outcome not in CYCLE_OUTCOMES:
        blocked.append(f"cycle_outcome_outside_vocabulary:{outcome}")

    if blocked or org is None or moment is None:
        return _result(cycle_id=str(cycle_id or "") or None, blocked_reasons=blocked)

    existing = _select_one(connection, org, str(cycle_id))
    if existing is None:
        return _result(cycle_id=str(cycle_id), blocked_reasons=[BLOCK_NOT_FOUND])

    current = dict(existing)
    if str(current.get("owner_id") or "") != str(owner_id):
        return _result(
            cycle_id=str(cycle_id),
            cycle=_row_to_cycle(existing, now=moment),
            blocked_reasons=[BLOCK_NOT_THE_OWNER],
        )

    supplied = counters or {}
    values: dict[str, Any] = {
        "cycle_status": RELEASED,
        "cycle_outcome": str(outcome),
        "released_at": moment,
        "completed_at": moment,
        "updated_at": moment,
    }
    # Only the counters this table is allowed to hold, and never the three the
    # database refuses. A caller cannot smuggle a completion through here
    # because `jobs_completed` is not in this list.
    for name in (
        "sources_seen",
        "jobs_created",
        "jobs_reused",
        "jobs_blocked",
        "jobs_claimed",
        "jobs_refused",
        "missed_windows_recovered",
        "duplicate_triggers_suppressed",
    ):
        if name in supplied:
            values[name] = max(0, int(supplied[name] or 0))

    connection.execute(
        sa.update(CYCLES)
        .where(
            sa.and_(
                CYCLES.c.organization_id == org,
                CYCLES.c.cycle_id == str(cycle_id),
                CYCLES.c.owner_id == str(owner_id),
                CYCLES.c.cycle_status == ACQUIRED,
            )
        )
        .values(**values)
    )
    after = _select_one(connection, org, str(cycle_id))
    if after is None or str(dict(after).get("cycle_status")) != RELEASED:
        return _result(
            cycle_id=str(cycle_id),
            cycle=None if after is None else _row_to_cycle(after, now=moment),
            blocked_reasons=["row_changed_under_this_release"],
        )
    return _result(
        cycle_id=str(cycle_id),
        cycle=_row_to_cycle(after, now=moment),
        released=True,
    )


def read_cycle(
    *,
    connection: Any = None,
    organization_id: Any = None,
    cycle_id: Any = None,
    now: Any = None,
) -> dict[str, Any]:
    """Read one cycle, with staleness derived against `now`."""
    org, blocked = _validate(
        connection=connection, organization_id=organization_id, cycle_id=cycle_id
    )
    if blocked or org is None:
        return _result(cycle_id=str(cycle_id or "") or None, blocked_reasons=blocked)

    row = _select_one(connection, org, str(cycle_id))
    if row is None:
        return _result(cycle_id=str(cycle_id), blocked_reasons=[BLOCK_NOT_FOUND])
    return _result(
        cycle_id=str(cycle_id), cycle=_row_to_cycle(row, now=_as_datetime(now))
    )


def read_last_served_slot(
    *,
    connection: Any = None,
    organization_id: Any = None,
    cadence: Any = None,
    now: Any = None,
) -> dict[str, Any]:
    """The highest slot index that has actually been SERVED.

    This is the history the trigger compares against, and getting it wrong
    makes the reclaim path unreachable. Gate 159 measured that: counting a row
    in any status meant a process that acquired a slot and crashed left an
    `acquired` row, every later process inside that slot was told
    `already_triggered`, and the expired ownership was never reclaimed.

    A slot with a crashed owner is UNFINISHED, not served:

    ```text
    counted       released                   somebody completed it
    counted       acquired, not yet expired  somebody is on it right now
    NOT counted   acquired, expired          the owner is gone; reclaimable
    NOT counted   expired / abandoned        explicitly given up
    ```

    `now` is required to tell the second case from the third, because expiry is
    derived against a clock rather than stored - a stored `stale` status would
    need a sweeper to keep it true.

    Without a clock this falls back to counting every row, which is the old
    behaviour and is reported in `served_definition` so a caller can tell.
    """
    org, blocked = _validate(connection=connection, organization_id=organization_id)
    if blocked or org is None:
        return _result(
            blocked_reasons=blocked,
            **{
                "last_served_slot_index": None,
                "cycles_recorded": 0,
                "unfinished_slot_count": 0,
            },
        )

    moment = _as_datetime(now)
    scope = [CYCLES.c.organization_id == org]
    if str(cadence or "").strip():
        # Slot indexes are only comparable within one cadence: index 5 at
        # daily and index 5 at hourly are different instants.
        scope.append(CYCLES.c.cadence == str(cadence))

    if moment is None:
        served_where = sa.and_(*scope)
        definition = "any_row_no_clock_supplied"
    else:
        served_where = sa.and_(
            *scope,
            sa.or_(
                CYCLES.c.cycle_status == RELEASED,
                sa.and_(
                    CYCLES.c.cycle_status == ACQUIRED,
                    CYCLES.c.expires_at.isnot(None),
                    CYCLES.c.expires_at > moment,
                ),
            ),
        )
        definition = "released_or_still_actively_owned"

    highest, count = connection.execute(
        sa.select(sa.func.max(CYCLES.c.slot_index), sa.func.count()).where(
            served_where
        )
    ).first() or (None, 0)

    # Counted separately so an operator can see that a slot is being skipped
    # BECAUSE its owner died, rather than wondering why it reran.
    unfinished = 0
    if moment is not None:
        unfinished = int(
            connection.execute(
                sa.select(sa.func.count()).where(
                    sa.and_(
                        *scope,
                        CYCLES.c.cycle_status == ACQUIRED,
                        sa.or_(
                            CYCLES.c.expires_at.is_(None),
                            CYCLES.c.expires_at <= moment,
                        ),
                    )
                )
            ).scalar()
            or 0
        )

    return _result(
        **{
            "last_served_slot_index": None if highest is None else int(highest),
            "cycles_recorded": int(count or 0),
            "unfinished_slot_count": unfinished,
            "served_definition": definition,
            "measured_at": moment,
            "cadence": None if cadence is None else str(cadence),
        }
    )


def list_stale_owners(
    *,
    connection: Any = None,
    organization_id: Any = None,
    now: Any = None,
    limit: int = 100,
) -> dict[str, Any]:
    """Cycles still marked owned whose expiry has passed.

    Derived from `expires_at` against the supplied clock, never from a stored
    `stale` flag that a sweeper would have to maintain.
    """
    org, blocked = _validate(connection=connection, organization_id=organization_id)
    moment = _as_datetime(now)
    if moment is None:
        blocked.append(BLOCK_NO_CLOCK)
    if blocked or org is None or moment is None:
        return _result(
            blocked_reasons=blocked, **{"stale_owners": [], "stale_owner_count": 0}
        )

    rows = list(
        connection.execute(
            sa.select(CYCLES)
            .where(
                sa.and_(
                    CYCLES.c.organization_id == org,
                    CYCLES.c.cycle_status == ACQUIRED,
                    CYCLES.c.expires_at.isnot(None),
                    CYCLES.c.expires_at <= moment,
                )
            )
            .order_by(CYCLES.c.expires_at)
            .limit(int(limit))
        ).mappings()
    )
    stale = [_row_to_cycle(row, now=moment) for row in rows]
    return _result(
        **{
            "stale_owners": stale,
            "stale_owner_count": len(stale),
            "measured_at": moment,
        }
    )


def count_cycles(
    *, connection: Any = None, organization_id: Any = None, now: Any = None
) -> dict[str, Any]:
    """Cycle counts by status, with every status present including the empties."""
    org, blocked = _validate(connection=connection, organization_id=organization_id)
    empty = {
        "by_status": dict.fromkeys(sorted(CYCLE_STATUSES), 0),
        "by_outcome": {},
        "total": 0,
        "owned_total": 0,
        "rows_claiming_a_completion": 0,
        "rows_claiming_a_collector": 0,
        "rows_claiming_a_live_call": 0,
        "total_reclaims": 0,
        "highest_slot_index": None,
    }
    if blocked or org is None:
        return _result(blocked_reasons=blocked, **empty)

    by_status = dict.fromkeys(sorted(CYCLE_STATUSES), 0)
    for row in connection.execute(
        sa.select(CYCLES.c.cycle_status, sa.func.count())
        .where(CYCLES.c.organization_id == org)
        .group_by(CYCLES.c.cycle_status)
    ):
        by_status[str(row[0])] = int(row[1])

    by_outcome: dict[str, int] = {}
    for row in connection.execute(
        sa.select(CYCLES.c.cycle_outcome, sa.func.count())
        .where(CYCLES.c.organization_id == org)
        .group_by(CYCLES.c.cycle_outcome)
    ):
        by_outcome[str(row[0])] = int(row[1])

    totals = connection.execute(
        sa.select(
            sa.func.coalesce(sa.func.sum(CYCLES.c.jobs_completed), 0),
            sa.func.coalesce(sa.func.sum(CYCLES.c.collectors_invoked), 0),
            sa.func.coalesce(sa.func.sum(CYCLES.c.live_source_calls), 0),
            sa.func.coalesce(sa.func.sum(CYCLES.c.reclaim_count), 0),
            sa.func.max(CYCLES.c.slot_index),
        ).where(CYCLES.c.organization_id == org)
    ).first() or (0, 0, 0, 0, None)

    return _result(
        **{
            "by_status": by_status,
            "by_outcome": dict(sorted(by_outcome.items())),
            "total": sum(by_status.values()),
            "owned_total": by_status[ACQUIRED],
            # Summed from the rows, not assumed from the constraint. The
            # constraint is what keeps them zero; this is what proves it.
            "rows_claiming_a_completion": int(totals[0] or 0),
            "rows_claiming_a_collector": int(totals[1] or 0),
            "rows_claiming_a_live_call": int(totals[2] or 0),
            "total_reclaims": int(totals[3] or 0),
            "highest_slot_index": None if totals[4] is None else int(totals[4]),
        }
    )


def orchestration_lock_invariant_failures(result: dict[str, Any]) -> list[str]:
    """Refuse a result that claims execution, or contradicts itself."""
    fails: list[str] = []

    for counter in (
        "collectors_invoked",
        "live_source_calls",
        "network_calls",
        "jobs_completed",
    ):
        if int(result.get(counter) or 0) != 0:
            fails.append(f"lock_claimed:{counter}={result.get(counter)}")
    if result.get("source_monitoring_live"):
        fails.append("lock_claimed:source_monitoring_live")

    if result.get("acquired") and result.get("blocked_reasons"):
        fails.append("acquired_alongside_blocked_reasons")
    if result.get("acquired") and result.get("duplicate_suppressed"):
        fails.append("acquired_and_suppressed_at_once")
    if result.get("reclaimed") and not result.get("acquired"):
        fails.append("reclaimed_without_acquiring")
    if result.get("released") and result.get("blocked_reasons"):
        fails.append("released_alongside_blocked_reasons")
    if result.get("duplicate_suppressed") and not result.get("blocked_reasons"):
        fails.append("suppressed_without_naming_a_reason")

    cycle = result.get("cycle") or {}
    if cycle:
        status = cycle.get("cycle_status")
        if status not in CYCLE_STATUSES:
            fails.append(f"row_status_outside_vocabulary:{status}")
        if status == ACQUIRED and not cycle.get("expires_at"):
            fails.append("an_owned_cycle_has_no_expiry_and_could_never_be_reclaimed")
        if status == ACQUIRED and not cycle.get("owner_id"):
            fails.append("an_owned_cycle_has_no_owner")
        if status == RELEASED and not cycle.get("released_at"):
            fails.append("a_released_cycle_has_no_release_timestamp")
        for counter in ("jobs_completed", "collectors_invoked", "live_source_calls"):
            if int(cycle.get(counter) or 0) != 0:
                fails.append(f"row_claimed:{counter}={cycle.get(counter)}")
        if cycle.get("is_owned") and cycle.get("ownership_is_expired"):
            fails.append("a_cycle_is_both_owned_and_expired")

    # A count result that reports any of the three refused values is reporting
    # something the database should have made impossible.
    for name in (
        "rows_claiming_a_completion",
        "rows_claiming_a_collector",
        "rows_claiming_a_live_call",
    ):
        if int(result.get(name) or 0) != 0:
            fails.append(f"count_reported:{name}={result.get(name)}")

    by_status = result.get("by_status") or {}
    if by_status and sum(by_status.values()) != int(result.get("total") or 0):
        fails.append("by_status_does_not_account_for_the_total")

    return sorted(set(fails))
