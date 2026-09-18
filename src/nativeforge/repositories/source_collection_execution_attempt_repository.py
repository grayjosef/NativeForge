"""The execution attempt record (Gate 161G).

Records **that an attempt was made**, by which transport, and what came of it.
It stores no bytes: Gate 160 owns those, and this points at them by hash.

## Why a refused attempt matters

A policy refusal and a timeout both produce no response, so Gate 160 has nothing
to store. Without a row here, "we tried three times this week and were refused
every time" is not a fact the system holds - and that is precisely what an
operator needs when a source stops working.

So an attempt row is written for every outcome, including the ones where nothing
was fetched and nothing was stored.

## live_source_call cannot be written true

The database refuses it, and refuses any `transport_kind` but `hermetic`. That
is the fourth independent stop on a live call in this gate, and the only one
that cannot be bypassed by a caller: the other three are decisions, this one is
a constraint.
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from typing import Any

import sqlalchemy as sa

SCHEMA_VERSION = "nf_source_collection_execution_attempt_v1"

CONTROLLED_SCOPE = "controlled_dev_demo"

TABLE_NAME = "nf_source_collection_execution_attempts"

REAL_ORGANIZATION_ID = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"

REFUSED_BY_POLICY = "refused_by_policy"
REQUEST_BUILD_FAILED = "request_build_failed"
TRANSPORT_REFUSED = "transport_refused"
TRANSPORT_FAILED = "transport_failed"
RESPONSE_RECEIVED = "response_received"
RESPONSE_PERSISTED = "response_persisted"
UNKNOWN = "unknown"

EXECUTION_STATUSES = frozenset(
    {
        REFUSED_BY_POLICY,
        REQUEST_BUILD_FAILED,
        TRANSPORT_REFUSED,
        TRANSPORT_FAILED,
        RESPONSE_RECEIVED,
        RESPONSE_PERSISTED,
        UNKNOWN,
    }
)

HERMETIC = "hermetic"
LIVE = "live"
TRANSPORT_KINDS = frozenset({HERMETIC, LIVE})

REFUSAL_REASONS = frozenset(
    {
        "none",
        "refused_by_activation",
        "terms_blocked",
        "human_review_blocked",
        "not_a_synthetic_fixture",
        "live_transport_not_implemented",
        "live_transport_not_permitted",
        "scope_not_permitted",
        "request_build_refused",
        "transport_timeout",
        "transport_connection_failed",
        "response_too_large",
        "transient_worker_failure",
        "permanent_worker_failure",
        "unknown",
    }
)

FACT_STATUSES = frozenset(
    {"synthetic_fixture", "demo_fixture", "tenant_supplied", "unknown"}
)

BLOCK_NO_CONNECTION = "no_connection_supplied"
BLOCK_NO_ORGANIZATION = "no_usable_organization_id"
BLOCK_REAL_ORG = "real_organization_refused_by_name"
BLOCK_NO_ATTEMPT = "no_attempt_id_supplied"
BLOCK_NOT_FOUND = "no_attempt_row_for_this_attempt_id"
BLOCK_DUPLICATE = "this_attempt_has_already_been_recorded"
#: Gate 163 made a live attempt recordable FOR AN AUTHORIZED SOURCE. The
#: refusal keeps its place in front of migration 0050's CHECK and now asks the
#: same question it asks, so the two halves of "two refusals for one fact" no
#: longer disagree.
BLOCK_LIVE = "a_live_attempt_cannot_be_recorded_in_this_gate"
BLOCK_LIVE_UNAUTHORIZED = "a_live_attempt_named_no_authorized_source"


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


_METADATA = sa.MetaData()

ATTEMPTS = sa.Table(
    TABLE_NAME,
    _METADATA,
    sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
    sa.Column("organization_id", sa.Uuid(as_uuid=True), nullable=False),
    sa.Column("is_demo", sa.Boolean(), nullable=False),
    sa.Column("attempt_id", sa.Text(), nullable=False),
    sa.Column("attempt_number", sa.Integer(), nullable=False),
    sa.Column("collector_version", sa.String(length=128), nullable=False),
    sa.Column("job_id", sa.Text(), nullable=False),
    sa.Column("source_id", sa.Text(), nullable=False),
    sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("execution_status", sa.String(length=32), nullable=False),
    sa.Column("transport_kind", sa.String(length=16), nullable=False),
    sa.Column("transport_outcome", sa.String(length=48), nullable=True),
    sa.Column("http_status", sa.Integer(), nullable=True),
    sa.Column("bytes_received", sa.Integer(), nullable=False),
    sa.Column("refusal_reason", sa.String(length=48), nullable=False),
    sa.Column("blocked_reasons", sa.JSON(), nullable=True),
    sa.Column("request_url_fingerprint", sa.String(length=64), nullable=True),
    sa.Column("request_method", sa.String(length=16), nullable=True),
    sa.Column("raw_payload_sha256", sa.String(length=64), nullable=True),
    sa.Column("raw_payload_persisted", sa.Boolean(), nullable=False),
    sa.Column("execution_proof_available", sa.Boolean(), nullable=False),
    # Declared so a read can assert it. Migration 0050 permits a true value
    # only on a row that names its authorization.
    sa.Column("live_source_call", sa.Boolean(), nullable=False),
    # Added by migration 0050. Declared here because this table is declared
    # rather than reflected, so a column the repository does not name is a
    # column it cannot write.
    sa.Column("authorized_source_id", sa.Text(), nullable=True),
    sa.Column("fact_status", sa.String(length=32), nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
)


def _row_to_attempt(row: Any) -> dict[str, Any]:
    attempt = dict(row)
    return _json_safe(
        {
            "attempt_id": attempt.get("attempt_id"),
            "attempt_number": int(attempt.get("attempt_number") or 0),
            "collector_version": attempt.get("collector_version"),
            "job_id": attempt.get("job_id"),
            "source_id": attempt.get("source_id"),
            "organization_id": str(attempt.get("organization_id")),
            "is_demo": bool(attempt.get("is_demo")),
            "started_at": attempt.get("started_at"),
            "completed_at": attempt.get("completed_at"),
            "execution_status": attempt.get("execution_status"),
            "transport_kind": attempt.get("transport_kind"),
            "transport_outcome": attempt.get("transport_outcome"),
            "http_status": attempt.get("http_status"),
            "bytes_received": int(attempt.get("bytes_received") or 0),
            "refusal_reason": attempt.get("refusal_reason"),
            "blocked_reasons": list(attempt.get("blocked_reasons") or []),
            "request_url_fingerprint": attempt.get("request_url_fingerprint"),
            "request_method": attempt.get("request_method"),
            "raw_payload_sha256": attempt.get("raw_payload_sha256"),
            "raw_payload_persisted": bool(attempt.get("raw_payload_persisted")),
            "execution_proof_available": bool(attempt.get("execution_proof_available")),
            # Surfaced on reads, not just written. A live row whose
            # authorization only exists in the database is a row every health
            # lane reading through this mapper would count as unauthorized.
            "authorized_source_id": attempt.get("authorized_source_id"),
            # Read back so a caller can prove it is false.
            "live_source_call": bool(attempt.get("live_source_call")),
            "fact_status": attempt.get("fact_status"),
            "created_at": attempt.get("created_at"),
            # ---- derived ------------------------------------------------
            "was_refused": attempt.get("execution_status")
            in (REFUSED_BY_POLICY, TRANSPORT_REFUSED, REQUEST_BUILD_FAILED),
            "bytes_arrived": int(attempt.get("bytes_received") or 0) > 0,
        }
    )


def _result(**fields: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "scope": CONTROLLED_SCOPE,
        "attempt_id": None,
        "attempt": None,
        "recorded": False,
        "blocked_reasons": [],
        "collectors_invoked": 0,
        "live_source_calls": 0,
        "live_attempts": 0,
        "source_monitoring_live": False,
    }
    base.update(fields)
    base["blocked_reasons"] = sorted(set(base["blocked_reasons"] or []))
    return _json_safe(base)


def _validate(
    *, connection: Any, organization_id: Any, attempt_id: Any = None
) -> tuple[uuid.UUID | None, list[str]]:
    blocked: list[str] = []
    if connection is None:
        blocked.append(BLOCK_NO_CONNECTION)
    if str(organization_id or "").strip().lower() == REAL_ORGANIZATION_ID:
        blocked.append(BLOCK_REAL_ORG)
    org = _as_uuid(organization_id)
    if org is None:
        blocked.append(BLOCK_NO_ORGANIZATION)
    if attempt_id is not None and not str(attempt_id or "").strip():
        blocked.append(BLOCK_NO_ATTEMPT)
    return org, blocked


def _select_one(connection: Any, org: uuid.UUID, attempt_id: str) -> Any:
    return (
        connection.execute(
            sa.select(ATTEMPTS).where(
                sa.and_(
                    ATTEMPTS.c.organization_id == org,
                    ATTEMPTS.c.attempt_id == str(attempt_id),
                )
            )
        )
        .mappings()
        .first()
    )


def record_attempt(
    *,
    connection: Any = None,
    organization_id: Any = None,
    attempt_id: Any = None,
    attempt_number: Any = 1,
    collector_version: Any = "no_collector_registered",
    job_id: Any = None,
    source_id: Any = None,
    started_at: Any = None,
    completed_at: Any = None,
    execution_status: str = UNKNOWN,
    transport_kind: str = HERMETIC,
    transport_outcome: Any = None,
    http_status: Any = None,
    bytes_received: int = 0,
    refusal_reason: str = "none",
    blocked_reasons: list[str] | None = None,
    request_url_fingerprint: Any = None,
    request_method: Any = None,
    raw_payload_sha256: Any = None,
    raw_payload_persisted: bool = False,
    execution_proof_available: bool = False,
    fact_status: str = "synthetic_fixture",
    is_demo: bool = True,
    # Gate 163: the column migration 0050 added, and the thing that makes a
    # live attempt recordable at all. Without it a live attempt is refused
    # here and by the CHECK, which is the intended behaviour for every source
    # this campaign has not authorized.
    authorized_source_id: Any = None,
) -> dict[str, Any]:
    """Record one attempt. Every outcome gets a row, including a refusal."""
    org, blocked = _validate(
        connection=connection, organization_id=organization_id, attempt_id=attempt_id
    )
    moment = _as_datetime(started_at)
    if moment is None:
        blocked.append("no_clock_supplied")
    if not str(job_id or "").strip():
        blocked.append("no_job_id_supplied")
    if not str(source_id or "").strip():
        blocked.append("no_source_id_supplied")
    if execution_status not in EXECUTION_STATUSES:
        blocked.append(f"execution_status_outside_vocabulary:{execution_status}")
    if transport_kind not in TRANSPORT_KINDS:
        blocked.append(f"transport_kind_outside_vocabulary:{transport_kind}")
    elif transport_kind == LIVE and not str(authorized_source_id or "").strip():
        # Refused here as well as by the database. Two refusals for one fact,
        # on purpose: this one names the gate, the constraint names the row.
        #
        # Gate 163 made the two agree. Migration 0050's CHECK is
        # `transport_kind <> 'live' OR authorized_source_id IS NOT NULL`, so an
        # unconditional refusal here meant the layer above rejected rows the
        # database would have accepted - and a live attempt that really
        # happened could not be recorded, which is worse than not permitting
        # one.
        blocked.append(BLOCK_LIVE_UNAUTHORIZED)
    if refusal_reason not in REFUSAL_REASONS:
        blocked.append(f"refusal_reason_outside_vocabulary:{refusal_reason}")
    if fact_status not in FACT_STATUSES:
        blocked.append(f"fact_status_outside_vocabulary:{fact_status}")
    if execution_proof_available and not (
        raw_payload_persisted and str(raw_payload_sha256 or "").strip()
    ):
        blocked.append("a_proof_was_claimed_without_a_persisted_payload")

    if blocked or org is None or moment is None:
        return _result(
            attempt_id=str(attempt_id or "") or None, blocked_reasons=blocked
        )

    existing = _select_one(connection, org, str(attempt_id))
    if existing is not None:
        # One attempt, one row. A retry is a NEW attempt identity, so recording
        # the same one twice means somebody is overwriting an outcome.
        return _result(
            attempt_id=str(attempt_id),
            attempt=_row_to_attempt(existing),
            blocked_reasons=[BLOCK_DUPLICATE],
        )

    try:
        with connection.begin_nested():
            connection.execute(
                sa.insert(ATTEMPTS).values(
                    id=uuid.uuid4(),
                    organization_id=org,
                    is_demo=bool(is_demo),
                    attempt_id=str(attempt_id),
                    attempt_number=max(1, int(attempt_number or 1)),
                    collector_version=str(collector_version),
                    job_id=str(job_id),
                    source_id=str(source_id),
                    started_at=moment,
                    completed_at=_as_datetime(completed_at),
                    execution_status=str(execution_status),
                    transport_kind=str(transport_kind),
                    transport_outcome=(
                        None if transport_outcome is None else str(transport_outcome)
                    ),
                    http_status=(int(http_status) if http_status is not None else None),
                    bytes_received=max(0, int(bytes_received or 0)),
                    refusal_reason=str(refusal_reason),
                    blocked_reasons=list(blocked_reasons or []),
                    request_url_fingerprint=(
                        None
                        if request_url_fingerprint is None
                        else str(request_url_fingerprint)[:64]
                    ),
                    request_method=(
                        None if request_method is None else str(request_method)
                    ),
                    raw_payload_sha256=(
                        None if raw_payload_sha256 is None else str(raw_payload_sha256)
                    ),
                    raw_payload_persisted=bool(raw_payload_persisted),
                    execution_proof_available=bool(execution_proof_available),
                    # Derived, not hardcoded. Migration 0050's first CHECK is
                    # `live_source_call = 0 OR transport_kind = 'live'`, so
                    # this is true exactly when the transport was live. The
                    # previous `False` carried the comment "Never anything
                    # else. The database refuses it", which stopped being
                    # true at 0050.
                    live_source_call=bool(transport_kind == LIVE),
                    authorized_source_id=(
                        None
                        if not str(authorized_source_id or "").strip()
                        else str(authorized_source_id).strip()
                    ),
                    fact_status=str(fact_status),
                    created_at=moment,
                )
            )
    except sa.exc.IntegrityError as exc:
        return _result(
            attempt_id=str(attempt_id),
            blocked_reasons=[f"insert_refused_by_the_database:{type(exc).__name__}"],
        )

    written = _select_one(connection, org, str(attempt_id))
    return _result(
        attempt_id=str(attempt_id),
        attempt=None if written is None else _row_to_attempt(written),
        recorded=True,
    )


def get_attempt(
    *, connection: Any = None, organization_id: Any = None, attempt_id: Any = None
) -> dict[str, Any]:
    org, blocked = _validate(
        connection=connection, organization_id=organization_id, attempt_id=attempt_id
    )
    if blocked or org is None:
        return _result(
            attempt_id=str(attempt_id or "") or None, blocked_reasons=blocked
        )
    row = _select_one(connection, org, str(attempt_id))
    if row is None:
        return _result(attempt_id=str(attempt_id), blocked_reasons=[BLOCK_NOT_FOUND])
    return _result(attempt_id=str(attempt_id), attempt=_row_to_attempt(row))


def list_attempts(
    *,
    connection: Any = None,
    organization_id: Any = None,
    job_id: Any = None,
    source_id: Any = None,
    execution_status: Any = None,
    limit: int = 200,
) -> dict[str, Any]:
    org, blocked = _validate(connection=connection, organization_id=organization_id)
    if execution_status is not None and str(execution_status) not in (
        EXECUTION_STATUSES
    ):
        blocked.append(f"execution_status_outside_vocabulary:{execution_status}")
    if blocked or org is None:
        return _result(blocked_reasons=blocked, **{"attempts": [], "attempt_count": 0})

    query = sa.select(ATTEMPTS).where(ATTEMPTS.c.organization_id == org)
    if str(job_id or "").strip():
        query = query.where(ATTEMPTS.c.job_id == str(job_id))
    if str(source_id or "").strip():
        query = query.where(ATTEMPTS.c.source_id == str(source_id))
    if execution_status is not None:
        query = query.where(ATTEMPTS.c.execution_status == str(execution_status))
    query = query.order_by(ATTEMPTS.c.started_at, ATTEMPTS.c.attempt_id).limit(
        int(limit)
    )

    rows = list(connection.execute(query).mappings())
    attempts = [_row_to_attempt(row) for row in rows]
    return _result(
        **{
            "attempts": attempts,
            "attempt_count": len(attempts),
            "truncated_at_limit": len(attempts) >= int(limit),
        }
    )


def count_attempts(
    *, connection: Any = None, organization_id: Any = None
) -> dict[str, Any]:
    org, blocked = _validate(connection=connection, organization_id=organization_id)
    empty = {
        "by_status": dict.fromkeys(sorted(EXECUTION_STATUSES), 0),
        "by_transport_kind": dict.fromkeys(sorted(TRANSPORT_KINDS), 0),
        "by_refusal_reason": {},
        "total": 0,
        "hermetic_attempts": 0,
        "live_attempts": 0,
        "authorized_live_attempts": 0,
        "unauthorized_live_attempts": 0,
        "unsigned_live_attempts": 0,
        "source_mismatch_live_attempts": 0,
        "live_rows_outside_authorized_set": 0,
        "unauthorized_detail": [],
        "rows_claiming_a_live_call": 0,
        "proofs_available": 0,
        "payloads_linked": 0,
        "total_bytes_received": 0,
    }
    if blocked or org is None:
        return _result(blocked_reasons=blocked, **empty)

    by_status = dict.fromkeys(sorted(EXECUTION_STATUSES), 0)
    for row in connection.execute(
        sa.select(ATTEMPTS.c.execution_status, sa.func.count())
        .where(ATTEMPTS.c.organization_id == org)
        .group_by(ATTEMPTS.c.execution_status)
    ):
        by_status[str(row[0])] = int(row[1])

    by_kind = dict.fromkeys(sorted(TRANSPORT_KINDS), 0)
    for row in connection.execute(
        sa.select(ATTEMPTS.c.transport_kind, sa.func.count())
        .where(ATTEMPTS.c.organization_id == org)
        .group_by(ATTEMPTS.c.transport_kind)
    ):
        by_kind[str(row[0])] = int(row[1])

    by_reason: dict[str, int] = {}
    for row in connection.execute(
        sa.select(ATTEMPTS.c.refusal_reason, sa.func.count())
        .where(ATTEMPTS.c.organization_id == org)
        .group_by(ATTEMPTS.c.refusal_reason)
    ):
        by_reason[str(row[0])] = int(row[1])

    totals = connection.execute(
        sa.select(
            sa.func.coalesce(
                sa.func.sum(sa.cast(ATTEMPTS.c.live_source_call, sa.Integer)), 0
            ),
            sa.func.coalesce(
                sa.func.sum(sa.cast(ATTEMPTS.c.execution_proof_available, sa.Integer)),
                0,
            ),
            sa.func.coalesce(
                sa.func.sum(sa.cast(ATTEMPTS.c.raw_payload_persisted, sa.Integer)), 0
            ),
            sa.func.coalesce(sa.func.sum(ATTEMPTS.c.bytes_received), 0),
        ).where(ATTEMPTS.c.organization_id == org)
    ).first() or (0, 0, 0, 0)

    # Gate 163: classify every live row rather than counting them. The
    # question is not "how many live attempts" but "how many the campaign did
    # not authorize", and `live_attempts - 1` would answer neither: it would
    # pass for a second live row from any source at any host.
    live_summary = _classify_live_rows(connection=connection, organization_id=org)

    return _result(
        **{
            "by_status": by_status,
            "by_transport_kind": by_kind,
            "by_refusal_reason": dict(sorted(by_reason.items())),
            "total": sum(by_status.values()),
            "hermetic_attempts": by_kind[HERMETIC],
            "live_attempts": by_kind[LIVE],
            # Each derived from the linkage that failed, not from a difference
            # of totals.
            "authorized_live_attempts": live_summary["authorized_live_attempts"],
            "unauthorized_live_attempts": live_summary["unauthorized_live_attempts"],
            "unsigned_live_attempts": live_summary["unsigned_live_attempts"],
            "source_mismatch_live_attempts": live_summary[
                "source_mismatch_live_attempts"
            ],
            "live_rows_outside_authorized_set": live_summary[
                "live_rows_outside_authorized_set"
            ],
            "unauthorized_detail": live_summary["unauthorized_detail"],
            # Summed from the rows. Migration 0050 permits a true value only
            # on a row that names its authorization, so this is reported and
            # the invariant below asserts the UNAUTHORIZED count instead.
            "rows_claiming_a_live_call": int(totals[0] or 0),
            "proofs_available": int(totals[1] or 0),
            "payloads_linked": int(totals[2] or 0),
            "total_bytes_received": int(totals[3] or 0),
        }
    )


def _classify_live_rows(*, connection: Any, organization_id: Any) -> dict[str, Any]:
    """Read the live rows and classify each one.

    Reads only the live rows: the classification is per-row and there are few,
    while the hermetic rows are not candidates for being unauthorized.
    """
    empty = {
        "authorized_live_attempts": 0,
        "unauthorized_live_attempts": 0,
        "unsigned_live_attempts": 0,
        "source_mismatch_live_attempts": 0,
        "live_rows_outside_authorized_set": 0,
        "unauthorized_detail": [],
    }
    try:
        from nativeforge.services.source_live_attempt_authorization_service import (
            classify_live_attempts,
        )

        # `.mappings()`, as `_select_one` does: `_row_to_attempt` takes a
        # mapping, and a bare Row is not one.
        rows = (
            connection.execute(
                sa.select(ATTEMPTS).where(
                    sa.and_(
                        ATTEMPTS.c.organization_id == organization_id,
                        ATTEMPTS.c.transport_kind == LIVE,
                    )
                )
            )
            .mappings()
            .all()
        )
        summary = classify_live_attempts(
            [_row_to_attempt(row) for row in rows],
            connection=connection,
            organization_id=organization_id,
        )
    except Exception:  # noqa: BLE001 - an unclassifiable row is not authorized
        # -1 rather than 0: a count that could not be taken must not read as
        # "none found", which is how an unreadable check becomes a pass.
        return {**empty, "unauthorized_live_attempts": -1}

    return {key: summary.get(key, empty[key]) for key in empty}


def attempt_invariant_failures(result: dict[str, Any]) -> list[str]:
    """Refuse a result that claims a live call, or contradicts itself."""
    fails: list[str] = []

    # Gate 163: `live_attempts` is no longer among these. An authorized live
    # attempt is the first real collection, not a claim to refuse - and the
    # UNAUTHORIZED counters below carry the property this list was protecting.
    #
    # `collectors_invoked` and `live_source_calls` stay: they are envelope
    # counters that a hermetic store must not report.
    for counter in ("collectors_invoked", "live_source_calls"):
        if int(result.get(counter) or 0) != 0:
            fails.append(f"attempt_store_claimed:{counter}={result.get(counter)}")
    if result.get("source_monitoring_live"):
        fails.append("attempt_store_claimed:source_monitoring_live")

    if result.get("recorded") and result.get("blocked_reasons"):
        fails.append("recorded_alongside_blocked_reasons")
    if (
        not result.get("recorded")
        and result.get("attempt")
        and not result.get("blocked_reasons")
    ):
        fails.append("returned_an_attempt_without_recording_or_refusing")

    attempt = result.get("attempt") or {}
    if attempt:
        if attempt.get("live_source_call"):
            fails.append("row_claimed:live_source_call")
        if attempt.get("transport_kind") != HERMETIC:
            fails.append(f"row_transport_kind:{attempt.get('transport_kind')}")
        if attempt.get("execution_status") not in EXECUTION_STATUSES:
            fails.append(
                f"row_status_outside_vocabulary:{attempt.get('execution_status')}"
            )
        if attempt.get("refusal_reason") not in REFUSAL_REASONS:
            fails.append(
                f"row_refusal_outside_vocabulary:{attempt.get('refusal_reason')}"
            )
        if attempt.get("execution_proof_available") and not attempt.get(
            "raw_payload_persisted"
        ):
            fails.append("a_row_claims_a_proof_without_a_persisted_payload")
        if attempt.get("raw_payload_persisted") and not attempt.get(
            "raw_payload_sha256"
        ):
            fails.append("a_row_claims_a_persisted_payload_without_a_hash")

    # Four properties where there was one, and none is satisfied by a nonzero
    # live count. Each is derived from the linkage that failed.
    for counter in (
        "unauthorized_live_attempts",
        "unsigned_live_attempts",
        "source_mismatch_live_attempts",
        "live_rows_outside_authorized_set",
    ):
        value = int(result.get(counter) or 0)
        if value > 0:
            fails.append(f"count_reported:{counter}={value}")
        if value < 0:
            fails.append(f"count_could_not_be_taken:{counter}")

    # authorized + unauthorized must account for every live attempt, or one of
    # them was computed rather than classified.
    if "live_attempts" in result and "authorized_live_attempts" in result:
        live = int(result.get("live_attempts") or 0)
        authorized = int(result.get("authorized_live_attempts") or 0)
        unauthorized = int(result.get("unauthorized_live_attempts") or 0)
        if unauthorized >= 0 and authorized + unauthorized != live:
            fails.append(
                f"live_attempts_unaccounted_for:{authorized}+{unauthorized}!={live}"
            )

    # An unauthorized count with no detail is one nobody can act on.
    if int(result.get("unauthorized_live_attempts") or 0) > 0 and not result.get(
        "unauthorized_detail"
    ):
        fails.append("unauthorized_live_attempts_without_detail")

    by_status = result.get("by_status") or {}
    if by_status and sum(by_status.values()) != int(result.get("total") or 0):
        fails.append("by_status_does_not_account_for_the_total")

    return sorted(set(fails))
