"""The raw payload store (Gate 160D).

## One attempt, one payload, and no silent overwrite

`ux_nf_source_collection_raw_payloads_attempt` is unique over
`(organization_id, attempt_id)`. So:

```text
same attempt, same bytes       idempotent - the existing row is returned
same attempt, DIFFERENT bytes  REFUSED, loudly
different attempt, same bytes  allowed, and the hash index shows the pair
```

The middle case is the one that matters. Two different byte strings claiming to
be the same attempt is a contradiction: either the attempt identity is wrong or
one of the bodies is. Overwriting would destroy the evidence that they
disagreed, and skipping would silently keep whichever arrived first. So it is
refused and both hashes are named.

The third case is deliberately allowed. Two attempts retrieving identical bytes
is normal - a source that has not changed - and refusing it would make an
unchanged source indistinguishable from a failed one.

## The hash is verified on write AND on read

```text
write   re-hash the bytes handed in, compare with the declared hash
read    re-hash the bytes read back, compare with the stored hash
```

A store that records a hash and never checks it again has recorded an intention.
The read-side check is what catches a body that changed underneath the row,
which is the tamper case the replay service exists to refuse.

## What it will not accept

`persist_payload` takes **filtered** metadata only. It does not filter headers
itself - `source_response_metadata_filter_service` does - but it refuses a call
whose metadata contains a header name outside the allowlist, so a caller that
skipped the filter cannot write through this door.

That is a second check on the same fact, and deliberately so: the filter answers
*which headers are safe*, and this answers *may I write these*. The second can
fail for a reason the first never sees, such as a caller assembling a dict by
hand.
"""

from __future__ import annotations

import base64
import json
import uuid
from datetime import UTC, datetime
from typing import Any

import sqlalchemy as sa

from nativeforge.services.source_raw_payload_hash_service import (
    MAX_PAYLOAD_BYTES,
    as_bytes,
    hash_payload,
    verify_payload,
)
from nativeforge.services.source_response_metadata_filter_service import (
    ALLOWED_RESPONSE_HEADERS,
    CREDENTIAL_HEADERS,
    normalize_header_name,
)

SCHEMA_VERSION = "nf_source_collection_raw_payload_store_v1"

CONTROLLED_SCOPE = "controlled_dev_demo"

TABLE_NAME = "nf_source_collection_raw_payloads"

#: Refused by name. Gate 135's authorization covers the demo org only.
REAL_ORGANIZATION_ID = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"

MODE_DATABASE = "controlled_dev_demo_database"
MODE_OBJECT_STORE = "object_store_reference"
MODE_NOT_STORED = "body_not_stored"

BODY_STORAGE_MODES = frozenset({MODE_DATABASE, MODE_OBJECT_STORE, MODE_NOT_STORED})

ACTIVE = "active"
ARCHIVED = "archived"
REFUSED = "refused"
UNKNOWN = "unknown"

PAYLOAD_STATUSES = frozenset({ACTIVE, ARCHIVED, REFUSED, UNKNOWN})

#: `retention_unknown` is the default. Nobody has approved a retention policy
#: for source evidence, and picking one here would be inventing it.
RETENTION_UNKNOWN = "retention_unknown"

RETENTION_POLICIES = frozenset(
    {
        RETENTION_UNKNOWN,
        "retain_7_days",
        "retain_90_days",
        "retain_1_year",
        "retain_indefinite",
    }
)

FACT_STATUSES = frozenset(
    {"demo_fixture", "synthetic_fixture", "tenant_supplied", "unknown"}
)

BLOCK_NO_CONNECTION = "no_connection_supplied"
BLOCK_NO_ORGANIZATION = "no_usable_organization_id"
BLOCK_REAL_ORG = "real_organization_refused_by_name"
BLOCK_NO_ATTEMPT = "no_attempt_id_supplied"
BLOCK_NOT_FOUND = "no_payload_row_for_this_attempt_id"
BLOCK_HASH_MISMATCH = "declared_hash_does_not_match_the_supplied_bytes"
BLOCK_DIFFERENT_BYTES = "this_attempt_already_stored_different_bytes"
BLOCK_OVERSIZE = "payload_exceeds_max_bytes"
BLOCK_UNSAFE_HEADER = "metadata_contains_a_header_outside_the_allowlist"
BLOCK_CREDENTIAL_HEADER = "metadata_contains_a_known_credential_header"


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


#: Declared, not reflected - Gate 157 lost the `sa.Uuid` decorator to
#: reflection and got "type 'UUID' is not supported" when binding a UUID.
_METADATA = sa.MetaData()

PAYLOADS = sa.Table(
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
    sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("response_status", sa.Integer(), nullable=True),
    sa.Column("media_type", sa.String(length=256), nullable=True),
    sa.Column("encoding", sa.String(length=64), nullable=True),
    sa.Column("source_url_fingerprint", sa.String(length=64), nullable=True),
    sa.Column("response_header_metadata", sa.JSON(), nullable=True),
    sa.Column("body_storage_mode", sa.String(length=48), nullable=False),
    sa.Column("body_bytes", sa.LargeBinary(), nullable=True),
    sa.Column("payload_size_bytes", sa.Integer(), nullable=False),
    sa.Column("payload_sha256", sa.String(length=64), nullable=False),
    sa.Column("payload_status", sa.String(length=32), nullable=False),
    sa.Column("retention_policy", sa.String(length=32), nullable=False),
    sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("parser_version", sa.String(length=64), nullable=True),
    sa.Column("blocked_reasons", sa.JSON(), nullable=True),
    # Declared so a read can assert them. The database refuses a true value.
    sa.Column("collector_invoked", sa.Boolean(), nullable=False),
    sa.Column("live_fetch_performed", sa.Boolean(), nullable=False),
    sa.Column("fact_status", sa.String(length=32), nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
)


def _row_to_payload(row: Any, *, include_body: bool = False) -> dict[str, Any]:
    payload = dict(row)
    body = payload.get("body_bytes")

    record = {
        "attempt_id": payload.get("attempt_id"),
        "attempt_number": int(payload.get("attempt_number") or 0),
        "collector_version": payload.get("collector_version"),
        "job_id": payload.get("job_id"),
        "source_id": payload.get("source_id"),
        "organization_id": str(payload.get("organization_id")),
        "is_demo": bool(payload.get("is_demo")),
        "received_at": payload.get("received_at"),
        "response_status": payload.get("response_status"),
        "media_type": payload.get("media_type"),
        "encoding": payload.get("encoding"),
        "source_url_fingerprint": payload.get("source_url_fingerprint"),
        "response_header_metadata": payload.get("response_header_metadata") or {},
        "body_storage_mode": payload.get("body_storage_mode"),
        "payload_size_bytes": int(payload.get("payload_size_bytes") or 0),
        "payload_sha256": payload.get("payload_sha256"),
        "payload_status": payload.get("payload_status"),
        "retention_policy": payload.get("retention_policy"),
        "archived_at": payload.get("archived_at"),
        "parser_version": payload.get("parser_version"),
        "blocked_reasons": list(payload.get("blocked_reasons") or []),
        # Read back so a caller can prove they are false rather than trust a
        # Python constant.
        "collector_invoked": bool(payload.get("collector_invoked")),
        "live_fetch_performed": bool(payload.get("live_fetch_performed")),
        "fact_status": payload.get("fact_status"),
        "created_at": payload.get("created_at"),
        "updated_at": payload.get("updated_at"),
        # ---- derived ----------------------------------------------------
        "has_body": body is not None,
        "is_archived": payload.get("payload_status") == ARCHIVED,
        "retention_is_unknown": payload.get("retention_policy") == RETENTION_UNKNOWN,
    }
    # The bytes come back only when asked for, so a metadata listing cannot
    # accidentally carry megabytes through a JSON envelope.
    result = _json_safe(record)
    if include_body:
        # base64, NOT the raw bytes. Everything in this module ends up in a
        # `_json_safe` envelope, and `json.dumps(default=str)` turns bytes into
        # a Python repr string - lossy, and not decodable back. Gate 160
        # measured exactly that: the hash verified and the returned body was
        # unusable.
        #
        # base64 survives the envelope and round-trips, which is what 160H
        # means by "a safe encoded representation".
        raw = b"" if body is None else bytes(body)
        result["body_base64"] = base64.b64encode(raw).decode("ascii")
        result["body_encoding"] = "base64"
    return result


def _result(**fields: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "scope": CONTROLLED_SCOPE,
        "attempt_id": None,
        "payload": None,
        "stored": False,
        "deduplicated": False,
        "archived": False,
        "hash_verified": False,
        "blocked_reasons": [],
        # Constants of this gate, asserted by the invariant checker against the
        # row that was written.
        "collectors_invoked": 0,
        "live_source_calls": 0,
        "network_calls": 0,
        "object_store_calls": 0,
        "object_store_configured": False,
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


def _check_metadata(metadata: Any) -> list[str]:
    """Refuse a caller that assembled metadata without the filter."""
    blocked: list[str] = []
    if not isinstance(metadata, dict):
        return blocked
    for name in metadata:
        normalized = normalize_header_name(name)
        if normalized in CREDENTIAL_HEADERS:
            blocked.append(f"{BLOCK_CREDENTIAL_HEADER}:{normalized}")
        elif normalized not in ALLOWED_RESPONSE_HEADERS:
            blocked.append(f"{BLOCK_UNSAFE_HEADER}:{normalized}")
    return blocked


def _select_one(connection: Any, org: uuid.UUID, attempt_id: str) -> Any:
    return (
        connection.execute(
            sa.select(PAYLOADS).where(
                sa.and_(
                    PAYLOADS.c.organization_id == org,
                    PAYLOADS.c.attempt_id == str(attempt_id),
                )
            )
        )
        .mappings()
        .first()
    )


def persist_payload(
    *,
    connection: Any = None,
    organization_id: Any = None,
    attempt_id: Any = None,
    attempt_number: Any = 1,
    collector_version: Any = "no_collector_registered",
    job_id: Any = None,
    source_id: Any = None,
    body: Any = None,
    declared_sha256: Any = None,
    received_at: Any = None,
    response_status: Any = None,
    media_type: Any = None,
    encoding: Any = None,
    source_url_fingerprint: Any = None,
    safe_response_metadata: dict[str, Any] | None = None,
    retention_policy: str = RETENTION_UNKNOWN,
    fact_status: str = "synthetic_fixture",
    is_demo: bool = True,
    max_bytes: int = MAX_PAYLOAD_BYTES,
) -> dict[str, Any]:
    """Store one attempt's bytes. Verifies the hash before and after."""
    org, blocked = _validate(
        connection=connection, organization_id=organization_id, attempt_id=attempt_id
    )
    moment = _as_datetime(received_at)
    if moment is None:
        blocked.append("no_clock_supplied")
    if not str(job_id or "").strip():
        blocked.append("no_job_id_supplied")
    if not str(source_id or "").strip():
        blocked.append("no_source_id_supplied")
    if retention_policy not in RETENTION_POLICIES:
        blocked.append(f"retention_policy_outside_vocabulary:{retention_policy}")
    if fact_status not in FACT_STATUSES:
        blocked.append(f"fact_status_outside_vocabulary:{fact_status}")

    metadata = dict(safe_response_metadata or {})
    blocked.extend(_check_metadata(metadata))

    hashed = hash_payload(body=body, max_bytes=max_bytes)
    if not hashed["usable"]:
        blocked.extend(hashed["blocked_reasons"])

    declared = str(declared_sha256 or "").strip().lower()
    actual = hashed.get("payload_sha256")
    if declared and actual and declared != actual:
        # The caller computed a hash from different bytes than it passed. That
        # is the exact failure content addressing exists to catch.
        blocked.append(f"{BLOCK_HASH_MISMATCH}:{declared[:12]}!={str(actual)[:12]}")

    if blocked or org is None or moment is None:
        return _result(
            attempt_id=str(attempt_id or "") or None, blocked_reasons=blocked
        )

    payload_bytes = as_bytes(body) or b""

    existing = _select_one(connection, org, str(attempt_id))
    if existing is not None:
        current = dict(existing)
        if str(current.get("payload_sha256")) == actual:
            # Same attempt, same bytes. Idempotent.
            return _result(
                attempt_id=str(attempt_id),
                payload=_row_to_payload(existing),
                deduplicated=True,
                hash_verified=True,
            )
        # Same attempt, DIFFERENT bytes. Refused, and both hashes named -
        # overwriting would destroy the evidence that they disagreed.
        return _result(
            attempt_id=str(attempt_id),
            payload=_row_to_payload(existing),
            blocked_reasons=[
                f"{BLOCK_DIFFERENT_BYTES}:"
                f"stored={str(current.get('payload_sha256'))[:12]} "
                f"offered={str(actual)[:12]}"
            ],
        )

    try:
        with connection.begin_nested():
            connection.execute(
                sa.insert(PAYLOADS).values(
                    id=uuid.uuid4(),
                    organization_id=org,
                    is_demo=bool(is_demo),
                    attempt_id=str(attempt_id),
                    attempt_number=max(1, int(attempt_number or 1)),
                    collector_version=str(collector_version),
                    job_id=str(job_id),
                    source_id=str(source_id),
                    received_at=moment,
                    response_status=(
                        int(response_status) if response_status is not None else None
                    ),
                    media_type=None if media_type is None else str(media_type),
                    encoding=None if encoding is None else str(encoding),
                    source_url_fingerprint=(
                        None
                        if source_url_fingerprint is None
                        else str(source_url_fingerprint)[:64]
                    ),
                    response_header_metadata=metadata,
                    body_storage_mode=MODE_DATABASE,
                    body_bytes=payload_bytes,
                    payload_size_bytes=int(hashed["payload_size_bytes"]),
                    payload_sha256=str(actual),
                    payload_status=ACTIVE,
                    retention_policy=str(retention_policy),
                    archived_at=None,
                    parser_version=None,
                    blocked_reasons=[],
                    # Never anything else. The database refuses it.
                    collector_invoked=False,
                    live_fetch_performed=False,
                    fact_status=str(fact_status),
                    created_at=moment,
                    updated_at=moment,
                )
            )
    except sa.exc.IntegrityError as exc:
        return _result(
            attempt_id=str(attempt_id),
            blocked_reasons=[f"insert_refused_by_the_database:{type(exc).__name__}"],
        )

    # Read it back and re-hash. A store that writes a hash and never checks it
    # again has recorded an intention rather than verified a fact.
    written = _select_one(connection, org, str(attempt_id))
    if written is None:
        return _result(
            attempt_id=str(attempt_id),
            blocked_reasons=["row_vanished_after_insert"],
        )
    readback = verify_payload(
        body=dict(written).get("body_bytes"), expected_sha256=actual
    )

    return _result(
        attempt_id=str(attempt_id),
        payload=_row_to_payload(written),
        stored=True,
        hash_verified=bool(readback["hash_verified"]),
        blocked_reasons=readback["blocked_reasons"],
        readback_sha256=readback["actual_sha256"],
    )


def get_payload(
    *,
    connection: Any = None,
    organization_id: Any = None,
    attempt_id: Any = None,
    include_body: bool = False,
) -> dict[str, Any]:
    """Read one payload by attempt, verifying the stored bytes still hash."""
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

    record = dict(row)
    readback = verify_payload(
        body=record.get("body_bytes"),
        expected_sha256=record.get("payload_sha256"),
    )
    result = _result(
        attempt_id=str(attempt_id),
        payload=_row_to_payload(row, include_body=include_body),
        hash_verified=bool(readback["hash_verified"]),
        blocked_reasons=readback["blocked_reasons"],
        readback_sha256=readback["actual_sha256"],
    )
    if include_body:
        # Attached AFTER `_result`, so it never passes through `_json_safe`.
        # A caller that wants the exact bytes gets the exact bytes; a caller
        # serializing this response uses `payload.body_base64` instead.
        raw = record.get("body_bytes")
        result["body_bytes"] = b"" if raw is None else bytes(raw)
    return result


def list_payloads(
    *,
    connection: Any = None,
    organization_id: Any = None,
    job_id: Any = None,
    source_id: Any = None,
    payload_sha256: Any = None,
    payload_status: Any = None,
    limit: int = 200,
) -> dict[str, Any]:
    """List payload metadata. Deterministically ordered, bodies excluded."""
    org, blocked = _validate(connection=connection, organization_id=organization_id)
    if payload_status is not None and str(payload_status) not in PAYLOAD_STATUSES:
        blocked.append(f"payload_status_outside_vocabulary:{payload_status}")
    if blocked or org is None:
        return _result(blocked_reasons=blocked, **{"payloads": [], "payload_count": 0})

    query = sa.select(PAYLOADS).where(PAYLOADS.c.organization_id == org)
    if str(job_id or "").strip():
        query = query.where(PAYLOADS.c.job_id == str(job_id))
    if str(source_id or "").strip():
        query = query.where(PAYLOADS.c.source_id == str(source_id))
    if str(payload_sha256 or "").strip():
        query = query.where(
            PAYLOADS.c.payload_sha256 == str(payload_sha256).strip().lower()
        )
    if payload_status is not None:
        query = query.where(PAYLOADS.c.payload_status == str(payload_status))

    # Deterministic: received_at then attempt_id, so two identical instants do
    # not order differently between runs.
    query = query.order_by(
        PAYLOADS.c.received_at, PAYLOADS.c.attempt_id
    ).limit(int(limit))

    rows = list(connection.execute(query).mappings())
    payloads = [_row_to_payload(row) for row in rows]
    return _result(
        **{
            "payloads": payloads,
            "payload_count": len(payloads),
            "truncated_at_limit": len(payloads) >= int(limit),
        }
    )


def archive_payload(
    *,
    connection: Any = None,
    organization_id: Any = None,
    attempt_id: Any = None,
    now: Any = None,
) -> dict[str, Any]:
    """Archive a payload. It stays readable; nothing here deletes.

    Deletion needs an approved retention policy and none exists, so archive is
    a lifecycle state rather than a removal.
    """
    org, blocked = _validate(
        connection=connection, organization_id=organization_id, attempt_id=attempt_id
    )
    moment = _as_datetime(now)
    if moment is None:
        blocked.append("no_clock_supplied")
    if blocked or org is None or moment is None:
        return _result(
            attempt_id=str(attempt_id or "") or None, blocked_reasons=blocked
        )

    row = _select_one(connection, org, str(attempt_id))
    if row is None:
        return _result(attempt_id=str(attempt_id), blocked_reasons=[BLOCK_NOT_FOUND])
    if str(dict(row).get("payload_status")) == ARCHIVED:
        return _result(
            attempt_id=str(attempt_id),
            payload=_row_to_payload(row),
            archived=True,
            deduplicated=True,
        )

    connection.execute(
        sa.update(PAYLOADS)
        .where(
            sa.and_(
                PAYLOADS.c.organization_id == org,
                PAYLOADS.c.attempt_id == str(attempt_id),
                PAYLOADS.c.payload_status == ACTIVE,
            )
        )
        .values(payload_status=ARCHIVED, archived_at=moment, updated_at=moment)
    )
    after = _select_one(connection, org, str(attempt_id))
    if after is None or str(dict(after).get("payload_status")) != ARCHIVED:
        return _result(
            attempt_id=str(attempt_id),
            blocked_reasons=["row_changed_under_this_archive"],
        )
    return _result(
        attempt_id=str(attempt_id), payload=_row_to_payload(after), archived=True
    )


def count_payloads(
    *, connection: Any = None, organization_id: Any = None
) -> dict[str, Any]:
    """Counts by status and storage mode, every bucket present."""
    org, blocked = _validate(connection=connection, organization_id=organization_id)
    empty = {
        "by_status": dict.fromkeys(sorted(PAYLOAD_STATUSES), 0),
        "by_storage_mode": dict.fromkeys(sorted(BODY_STORAGE_MODES), 0),
        "by_retention_policy": {},
        "total": 0,
        "total_bytes": 0,
        "distinct_hashes": 0,
        "rows_claiming_a_collector": 0,
        "rows_claiming_a_live_fetch": 0,
        "rows_over_the_size_limit": 0,
    }
    if blocked or org is None:
        return _result(blocked_reasons=blocked, **empty)

    by_status = dict.fromkeys(sorted(PAYLOAD_STATUSES), 0)
    for row in connection.execute(
        sa.select(PAYLOADS.c.payload_status, sa.func.count())
        .where(PAYLOADS.c.organization_id == org)
        .group_by(PAYLOADS.c.payload_status)
    ):
        by_status[str(row[0])] = int(row[1])

    by_mode = dict.fromkeys(sorted(BODY_STORAGE_MODES), 0)
    for row in connection.execute(
        sa.select(PAYLOADS.c.body_storage_mode, sa.func.count())
        .where(PAYLOADS.c.organization_id == org)
        .group_by(PAYLOADS.c.body_storage_mode)
    ):
        by_mode[str(row[0])] = int(row[1])

    by_retention: dict[str, int] = {}
    for row in connection.execute(
        sa.select(PAYLOADS.c.retention_policy, sa.func.count())
        .where(PAYLOADS.c.organization_id == org)
        .group_by(PAYLOADS.c.retention_policy)
    ):
        by_retention[str(row[0])] = int(row[1])

    totals = connection.execute(
        sa.select(
            sa.func.coalesce(sa.func.sum(PAYLOADS.c.payload_size_bytes), 0),
            sa.func.count(sa.distinct(PAYLOADS.c.payload_sha256)),
            sa.func.coalesce(
                sa.func.sum(sa.cast(PAYLOADS.c.collector_invoked, sa.Integer)), 0
            ),
            sa.func.coalesce(
                sa.func.sum(sa.cast(PAYLOADS.c.live_fetch_performed, sa.Integer)), 0
            ),
        ).where(PAYLOADS.c.organization_id == org)
    ).first() or (0, 0, 0, 0)

    oversize = int(
        connection.execute(
            sa.select(sa.func.count())
            .select_from(PAYLOADS)
            .where(
                sa.and_(
                    PAYLOADS.c.organization_id == org,
                    PAYLOADS.c.payload_size_bytes > MAX_PAYLOAD_BYTES,
                )
            )
        ).scalar()
        or 0
    )

    return _result(
        **{
            "by_status": by_status,
            "by_storage_mode": by_mode,
            "by_retention_policy": dict(sorted(by_retention.items())),
            "total": sum(by_status.values()),
            "total_bytes": int(totals[0] or 0),
            # Two attempts may share bytes, so this is deliberately not the
            # same as `total`.
            "distinct_hashes": int(totals[1] or 0),
            # Summed from the rows. The CHECK keeps them zero; this proves it.
            "rows_claiming_a_collector": int(totals[2] or 0),
            "rows_claiming_a_live_fetch": int(totals[3] or 0),
            "rows_over_the_size_limit": oversize,
            "max_payload_bytes": MAX_PAYLOAD_BYTES,
        }
    )


def raw_payload_invariant_failures(result: dict[str, Any]) -> list[str]:
    """Refuse a result that claims a fetch, or contradicts itself."""
    fails: list[str] = []

    for counter in (
        "collectors_invoked",
        "live_source_calls",
        "network_calls",
        "object_store_calls",
    ):
        if int(result.get(counter) or 0) != 0:
            fails.append(f"store_claimed:{counter}={result.get(counter)}")
    if result.get("source_monitoring_live"):
        fails.append("store_claimed:source_monitoring_live")
    if result.get("object_store_configured"):
        fails.append("store_claimed:object_store_configured")

    if result.get("stored") and result.get("blocked_reasons"):
        fails.append("stored_alongside_blocked_reasons")
    if result.get("stored") and result.get("deduplicated"):
        fails.append("stored_and_deduplicated_at_once")
    if result.get("stored") and not result.get("hash_verified"):
        fails.append("stored_without_verifying_the_readback_hash")

    payload = result.get("payload") or {}
    if payload:
        status = payload.get("payload_status")
        if status not in PAYLOAD_STATUSES:
            fails.append(f"row_status_outside_vocabulary:{status}")
        if payload.get("body_storage_mode") not in BODY_STORAGE_MODES:
            fails.append(
                f"row_storage_mode_outside_vocabulary:"
                f"{payload.get('body_storage_mode')}"
            )
        if payload.get("retention_policy") not in RETENTION_POLICIES:
            fails.append(
                f"row_retention_outside_vocabulary:{payload.get('retention_policy')}"
            )
        if payload.get("collector_invoked"):
            fails.append("row_claimed:collector_invoked")
        if payload.get("live_fetch_performed"):
            fails.append("row_claimed:live_fetch_performed")
        if status == ARCHIVED and not payload.get("archived_at"):
            fails.append("archived_row_without_a_timestamp")
        if status != ARCHIVED and payload.get("archived_at"):
            fails.append("unarchived_row_carrying_an_archived_at")
        size = int(payload.get("payload_size_bytes") or 0)
        if size > MAX_PAYLOAD_BYTES:
            fails.append(f"row_exceeds_the_size_limit:{size}")
        digest = str(payload.get("payload_sha256") or "")
        if len(digest) != 64:
            fails.append(f"row_hash_is_not_a_sha256_digest:{len(digest)}")
        # Nothing stored may carry an unsafe header name.
        for name in payload.get("response_header_metadata") or {}:
            normalized = normalize_header_name(name)
            if normalized in CREDENTIAL_HEADERS:
                fails.append(f"row_stored_a_credential_header:{normalized}")
            elif normalized not in ALLOWED_RESPONSE_HEADERS:
                fails.append(f"row_stored_an_unallowlisted_header:{normalized}")

    for name in ("rows_claiming_a_collector", "rows_claiming_a_live_fetch"):
        if int(result.get(name) or 0) != 0:
            fails.append(f"count_reported:{name}={result.get(name)}")
    if int(result.get("rows_over_the_size_limit") or 0) != 0:
        fails.append("count_reported_a_row_over_the_size_limit")

    by_status = result.get("by_status") or {}
    if by_status and sum(by_status.values()) != int(result.get("total") or 0):
        fails.append("by_status_does_not_account_for_the_total")

    return sorted(set(fails))
