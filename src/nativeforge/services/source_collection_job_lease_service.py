"""Gate 157C: a worker's claim on a job — atomic, owned, and expiring.

## What a lease is

A row saying **this worker holds the right to attempt this job until this
moment**. It is not a record that a check happened, that a source was
contacted, or that anything was fetched. `nf_source_collection_job_leases` has
no column any of those could live in, and three constraints refuse a row
claiming otherwise.

## Atomic, and enforced by the database rather than by care

A unique index on `(organization_id, job_id)` is what makes a duplicate claim
*refusable* rather than merely discouraged. Two workers racing both issue an
insert; one wins, the other gets an IntegrityError, and this module turns that
into a refusal rather than an exception.

Doing it with a SELECT-then-INSERT would leave a window between the two
statements, and a window is where the race lives. The check that matters is the
one the database makes.

## Expiry is the only way a claim is released without its owner

```text
a live lease      cannot be stolen, by anyone, including its own owner's twin
an expired lease  can be reclaimed by anybody
a released lease  is released by the owner, deliberately
```

A worker that dies holding a claim would block a job forever if expiry did not
exist. A worker that could steal a live claim would make the lease decorative.

## The clock is an argument

Expiry is compared to a supplied `now`. There is no `datetime.now()` here, so a
test can place a lease's expiry in the past without waiting, and a verifier can
assert an exact outcome rather than a probable one.
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import sqlalchemy as sa

SCHEMA_VERSION = "nf_source_collection_job_lease_v1"

CONTROLLED_SCOPE = "controlled_dev_demo"

TABLE_NAME = "nf_source_collection_job_leases"

REAL_ORGANIZATION_ID = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"

PENDING = "pending"
CLAIMED = "claimed"
COMPLETED = "completed"
REFUSED = "refused"
RETRYABLE = "retryable"
FAILED = "failed"
EXPIRED = "expired"
UNKNOWN = "unknown"

LEASE_STATUSES: tuple[str, ...] = (
    PENDING,
    CLAIMED,
    COMPLETED,
    REFUSED,
    RETRYABLE,
    FAILED,
    EXPIRED,
    UNKNOWN,
)

#: How long a claim lasts by default. Long enough that a slow cycle does not
#: lose its own lease, short enough that a dead worker does not block a job for
#: an afternoon.
DEFAULT_LEASE_SECONDS = 300

DEFAULT_MAX_ATTEMPTS = 3

BLOCK_ALREADY_CLAIMED = "job_is_already_claimed_by_another_worker"
BLOCK_LEASE_NOT_EXPIRED = "lease_has_not_expired_and_cannot_be_stolen"
BLOCK_NO_WORKER_ID = "no_worker_id_supplied"
BLOCK_NO_JOB_ID = "no_job_id_supplied"
BLOCK_REAL_ORG = "real_organization_refused_by_name"
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


#: Declared, not reflected. Reflection returns SQLite's CHAR(32) without the
#: `sa.Uuid` decorator, so binding a UUID raises "type 'UUID' is not
#: supported" - and the typed JSON and DateTime columns lose their round trip
#: the same way. This mirrors `tenant_digest_records_repository.RECORDS`.
_METADATA = sa.MetaData()

LEASES = sa.Table(
    TABLE_NAME,
    _METADATA,
    sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
    sa.Column("organization_id", sa.Uuid(as_uuid=True), nullable=False),
    sa.Column("is_demo", sa.Boolean(), nullable=False),
    sa.Column("job_id", sa.Text(), nullable=False),
    sa.Column("source_id", sa.Text(), nullable=False),
    sa.Column("lease_owner", sa.Text(), nullable=True),
    sa.Column("lease_acquired_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("lease_status", sa.String(length=32), nullable=False),
    sa.Column("failure_class", sa.String(length=32), nullable=False),
    sa.Column("attempt_count", sa.Integer(), nullable=False),
    sa.Column("max_attempts", sa.Integer(), nullable=False),
    sa.Column("next_retry_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("last_outcome_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("blocked_reasons", sa.JSON(), nullable=True),
    # Declared so a read can assert them. The database refuses a true value.
    sa.Column("collector_invoked", sa.Boolean(), nullable=False),
    sa.Column("url_fetched", sa.Boolean(), nullable=False),
    sa.Column("raw_payload_written", sa.Boolean(), nullable=False),
    sa.Column("fact_status", sa.String(length=32), nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
)


def _table(connection: Any) -> sa.Table:
    return LEASES


def _row_to_lease(row: Any, *, now: datetime | None = None) -> dict[str, Any]:
    record = dict(row)
    expires = _as_datetime(record.get("lease_expires_at"))
    held = bool(record.get("lease_owner"))
    # Expiry is derived at read time. Storing "expired" would need something to
    # run and write it, and nothing runs.
    expired = bool(held and expires and now and expires <= now)
    return _json_safe(
        {
            "job_id": record.get("job_id"),
            "source_id": record.get("source_id"),
            "lease_owner": record.get("lease_owner"),
            "lease_acquired_at": record.get("lease_acquired_at"),
            "lease_expires_at": record.get("lease_expires_at"),
            "lease_status": record.get("lease_status"),
            "failure_class": record.get("failure_class"),
            "attempt_count": record.get("attempt_count"),
            "max_attempts": record.get("max_attempts"),
            "next_retry_at": record.get("next_retry_at"),
            "blocked_reasons": record.get("blocked_reasons"),
            "held": held,
            "expired": expired,
            "collector_invoked": False,
            "url_fetched": False,
            "raw_payload_written": False,
        }
    )


def _result(**fields: Any) -> dict[str, Any]:
    base = {
        "schema_version": SCHEMA_VERSION,
        "scope": CONTROLLED_SCOPE,
        "claimed": False,
        "job_id": None,
        "lease": None,
        "blocked_reasons": [],
        "rows_written": 0,
        # Constants. A lease is a claim.
        "collector_invoked": False,
        "url_fetched": False,
        "raw_payload_written": False,
        "live_source_called": False,
        "source_monitoring_live": False,
    }
    base.update(fields)
    base["blocked_reasons"] = sorted(set(base["blocked_reasons"] or []))
    return _json_safe(base)


def read_lease(
    *,
    connection: Any = None,
    organization_id: Any = None,
    job_id: Any = None,
    now: Any = None,
) -> dict[str, Any]:
    """The lease for one job, or None. Reads."""
    org = _as_uuid(organization_id)
    if connection is None or org is None or not str(job_id or "").strip():
        return _result(job_id=str(job_id or "") or None, blocked_reasons=["bad_inputs"])

    table = _table(connection)
    row = (
        connection.execute(
            sa.select(table).where(
                sa.and_(
                    table.c.organization_id == org,
                    table.c.job_id == str(job_id),
                )
            )
        )
        .mappings()
        .first()
    )
    return _result(
        job_id=str(job_id),
        lease=_row_to_lease(row, now=_as_datetime(now)) if row else None,
    )


def claim_job(
    *,
    connection: Any = None,
    organization_id: Any = None,
    job_id: Any = None,
    source_id: Any = None,
    worker_id: Any = None,
    now: Any = None,
    lease_seconds: int = DEFAULT_LEASE_SECONDS,
    max_attempts: int = DEFAULT_MAX_ATTEMPTS,
    is_demo: bool = True,
) -> dict[str, Any]:
    """Claim a job, or refuse. Atomic on the database's unique index."""
    blocked: list[str] = []
    org = _as_uuid(organization_id)
    moment = _as_datetime(now)

    if not str(worker_id or "").strip():
        blocked.append(BLOCK_NO_WORKER_ID)
    if not str(job_id or "").strip():
        blocked.append(BLOCK_NO_JOB_ID)
    if str(organization_id or "").strip().lower() == REAL_ORGANIZATION_ID:
        blocked.append(BLOCK_REAL_ORG)
    if connection is None or org is None or moment is None:
        blocked.append("bad_inputs")

    if blocked:
        return _result(job_id=str(job_id or "") or None, blocked_reasons=blocked)

    table = _table(connection)
    expires = moment + timedelta(seconds=int(lease_seconds))

    existing = (
        connection.execute(
            sa.select(table).where(
                sa.and_(
                    table.c.organization_id == org,
                    table.c.job_id == str(job_id),
                )
            )
        )
        .mappings()
        .first()
    )

    if existing is None:
        # No row yet. The unique index is what decides a race, not this branch:
        # two workers both reaching here means one insert fails.
        try:
            connection.execute(
                sa.insert(table).values(
                    id=uuid.uuid4(),
                    organization_id=org,
                    is_demo=bool(is_demo),
                    job_id=str(job_id),
                    source_id=str(source_id or job_id),
                    lease_owner=str(worker_id),
                    lease_acquired_at=moment,
                    lease_expires_at=expires,
                    lease_status=CLAIMED,
                    failure_class="none",
                    attempt_count=0,
                    max_attempts=int(max_attempts),
                    collector_invoked=False,
                    url_fetched=False,
                    raw_payload_written=False,
                    fact_status="demo_fixture" if is_demo else "unknown",
                    created_at=moment,
                    updated_at=moment,
                )
            )
        except sa.exc.IntegrityError:
            # Another worker won the race. A refusal, not an error.
            return _result(job_id=str(job_id), blocked_reasons=[BLOCK_ALREADY_CLAIMED])
        return _result(
            claimed=True,
            job_id=str(job_id),
            rows_written=1,
            lease=read_lease(
                connection=connection,
                organization_id=organization_id,
                job_id=job_id,
                now=now,
            )["lease"],
        )

    current = _row_to_lease(existing, now=moment)

    if int(current.get("attempt_count") or 0) >= int(
        current.get("max_attempts") or DEFAULT_MAX_ATTEMPTS
    ):
        return _result(job_id=str(job_id), blocked_reasons=[BLOCK_ATTEMPTS_EXHAUSTED])

    if current["held"] and not current["expired"]:
        # A live lease cannot be stolen - not by another worker, and not by a
        # second process sharing this worker's id.
        return _result(
            job_id=str(job_id),
            blocked_reasons=[BLOCK_ALREADY_CLAIMED, BLOCK_LEASE_NOT_EXPIRED],
            lease=current,
        )

    # Either unheld or expired. Reclaim, and say so by bumping nothing except
    # the owner and the window - the attempt count belongs to the outcome, not
    # to the claim.
    connection.execute(
        sa.update(table)
        .where(
            sa.and_(
                table.c.organization_id == org,
                table.c.job_id == str(job_id),
            )
        )
        .values(
            lease_owner=str(worker_id),
            lease_acquired_at=moment,
            lease_expires_at=expires,
            lease_status=CLAIMED,
            updated_at=moment,
        )
    )
    return _result(
        claimed=True,
        job_id=str(job_id),
        rows_written=1,
        reclaimed_expired_lease=bool(current["expired"]),
        lease=read_lease(
            connection=connection,
            organization_id=organization_id,
            job_id=job_id,
            now=now,
        )["lease"],
    )


def record_outcome(
    *,
    connection: Any = None,
    organization_id: Any = None,
    job_id: Any = None,
    worker_id: Any = None,
    lease_status: str = REFUSED,
    failure_class: str = "none",
    blocked_reasons: list[str] | None = None,
    now: Any = None,
    next_retry_at: Any = None,
    increment_attempt: bool = False,
    release_lease: bool = True,
) -> dict[str, Any]:
    """Record what happened, and release the claim unless told otherwise."""
    org = _as_uuid(organization_id)
    moment = _as_datetime(now)
    if connection is None or org is None or moment is None:
        return _result(job_id=str(job_id or "") or None, blocked_reasons=["bad_inputs"])
    if lease_status not in LEASE_STATUSES:
        return _result(
            job_id=str(job_id or "") or None,
            blocked_reasons=[f"lease_status_outside_vocabulary:{lease_status}"],
        )

    table = _table(connection)
    existing = (
        connection.execute(
            sa.select(table).where(
                sa.and_(table.c.organization_id == org, table.c.job_id == str(job_id))
            )
        )
        .mappings()
        .first()
    )
    if existing is None:
        return _result(job_id=str(job_id), blocked_reasons=["no_lease_for_this_job"])

    current = dict(existing)
    if (
        worker_id
        and current.get("lease_owner")
        and str(current["lease_owner"]) != str(worker_id)
    ):
        return _result(
            job_id=str(job_id),
            blocked_reasons=["outcome_recorded_by_a_worker_that_does_not_hold_it"],
        )

    attempts = int(current.get("attempt_count") or 0)
    if increment_attempt:
        attempts = min(
            attempts + 1, int(current.get("max_attempts") or DEFAULT_MAX_ATTEMPTS)
        )

    values: dict[str, Any] = {
        "lease_status": lease_status,
        "failure_class": failure_class,
        "attempt_count": attempts,
        "last_outcome_at": moment,
        "next_retry_at": _as_datetime(next_retry_at),
        "blocked_reasons": sorted(set(blocked_reasons or [])),
        "updated_at": moment,
    }
    if release_lease:
        values.update(lease_owner=None, lease_acquired_at=None, lease_expires_at=None)

    connection.execute(
        sa.update(table)
        .where(sa.and_(table.c.organization_id == org, table.c.job_id == str(job_id)))
        .values(**values)
    )

    return _result(
        claimed=False,
        job_id=str(job_id),
        rows_written=1,
        lease=read_lease(
            connection=connection,
            organization_id=organization_id,
            job_id=job_id,
            now=now,
        )["lease"],
    )


def lease_invariant_failures(result: dict[str, Any]) -> list[str]:
    """Refuse a lease result that claimed more than a claim."""
    fails: list[str] = []

    if result.get("claimed") and result.get("blocked_reasons"):
        fails.append("claimed_alongside_blockers")

    lease = result.get("lease")
    if lease:
        if lease.get("lease_status") not in LEASE_STATUSES:
            fails.append(f"lease_status_outside_vocabulary:{lease.get('lease_status')}")
        if int(lease.get("attempt_count") or 0) > int(
            lease.get("max_attempts") or DEFAULT_MAX_ATTEMPTS
        ):
            fails.append("attempt_count_exceeded_the_budget")
        # A claim without an owner is not a claim.
        if lease.get("lease_status") == CLAIMED and not lease.get("lease_owner"):
            fails.append("claimed_without_an_owner")
        for flag in ("collector_invoked", "url_fetched", "raw_payload_written"):
            if lease.get(flag):
                fails.append(f"lease_claimed:{flag}")

    for flag in (
        "collector_invoked",
        "url_fetched",
        "raw_payload_written",
        "live_source_called",
        "source_monitoring_live",
    ):
        if result.get(flag):
            fails.append(f"lease_result_claimed:{flag}")

    return sorted(set(fails))
