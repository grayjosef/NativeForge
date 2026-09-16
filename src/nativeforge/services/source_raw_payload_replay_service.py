"""Raw payload replay (Gate 160H).

## The hash is checked BEFORE the bytes are returned

```text
read the row
re-hash the stored bytes
compare with the recorded hash
   match     -> return the bytes
   mismatch  -> return NOTHING, and say why
```

That order is the whole service. Returning bytes and reporting `hash_verified:
false` beside them would put the caller in the position of noticing, and a
caller that forgets has just replayed evidence that changed underneath the row.
So a tampered payload comes back with no body at all.

## Provenance is resolved, not asserted

```text
attempt -> job -> source
```

The row carries `job_id` and `source_id`, but carrying an id is not the same as
that id resolving to anything. `linked_job_found` and `linked_source_found` are
answered by **looking** - in Gate 158's job store and in the source registry -
so a payload pointing at a job nobody created is reported as such rather than
passing because the column was populated.

## Cross-organization access is refused by scoping, not by checking

Every query is scoped to `organization_id`, so a payload belonging to another
organization is not found rather than found-and-refused. A refusal that has to
compare two values is a refusal somebody can forget to write; a query that
cannot see the row cannot return it.

## An archived payload is still replayable

Archive is a lifecycle state, not a deletion. Nothing in this campaign has an
approved retention policy, so nothing deletes, and `archived` means "not part of
the working set" rather than "gone".
"""

from __future__ import annotations

import json
import uuid
from typing import Any

import sqlalchemy as sa

from nativeforge.repositories.source_collection_job_repository import (
    JOBS,
)
from nativeforge.repositories.source_collection_raw_payload_repository import (
    ARCHIVED,
    get_payload,
    raw_payload_invariant_failures,
)

SCHEMA_VERSION = "nf_source_raw_payload_replay_v1"

CONTROLLED_SCOPE = "controlled_dev_demo"

BLOCK_NOT_FOUND = "no_payload_for_this_attempt_in_this_organization"
BLOCK_TAMPERED = "stored_bytes_do_not_match_the_recorded_hash"
BLOCK_NO_BODY = "the_row_holds_no_body_to_replay"


def _json_safe(value: Any) -> Any:
    return json.loads(json.dumps(value, default=str, sort_keys=True))


def _job_exists(connection: Any, organization_id: Any, job_id: Any) -> bool:
    """Ask Gate 158's store, rather than trusting the column.

    The organization id arrives as a STRING - `_row_to_payload` stringifies it
    and the JSON envelope keeps it that way - while `JOBS.c.organization_id` is
    a typed `sa.Uuid` stored dashless. Comparing the two directly matches
    nothing, which Gate 160 measured as a provenance check that said "no such
    job" about a job it had just created.

    A provenance check that always answers no is as useless as one that always
    answers yes, and rather more convincing.
    """
    try:
        org = uuid.UUID(str(organization_id))
    except (ValueError, AttributeError, TypeError):
        return False
    try:
        found = connection.execute(
            sa.select(sa.func.count())
            .select_from(JOBS)
            .where(
                sa.and_(
                    JOBS.c.organization_id == org,
                    JOBS.c.job_id == str(job_id),
                )
            )
        ).scalar()
    except Exception:  # noqa: BLE001 - an unresolvable link is reported, not raised
        return False
    return bool(found)


def _source_known(source_id: Any) -> bool:
    """Ask the source registry, rather than trusting the column."""
    try:
        from nativeforge.services.source_monitoring_approved_source_service import (
            load_registry_rows,
        )
    except ImportError:  # pragma: no cover - the registry is part of the repo
        return False
    try:
        return str(source_id) in set(load_registry_rows())
    except Exception:  # noqa: BLE001
        return False


def _result(**fields: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "scope": CONTROLLED_SCOPE,
        "attempt_id": None,
        "replayable": False,
        "hash_verified": False,
        "linked_job_found": False,
        "linked_source_found": False,
        "archived": False,
        "readable": False,
        "body_base64": None,
        "payload_sha256": None,
        "payload_size_bytes": None,
        "blocked_reasons": [],
        "provenance": None,
        # Constants. Replay reads what is already stored.
        "collectors_invoked": 0,
        "live_source_calls": 0,
        "network_calls": 0,
        "urls_fetched": 0,
        "object_store_calls": 0,
        "object_store_configured": False,
        "is_execution_proof": False,
        "source_monitoring_live": False,
    }
    base.update(fields)
    base["blocked_reasons"] = sorted(set(base["blocked_reasons"] or []))
    return _json_safe(base)


def replay_payload(
    *,
    connection: Any = None,
    organization_id: Any = None,
    attempt_id: Any = None,
    include_body: bool = True,
) -> dict[str, Any]:
    """Return the exact stored bytes, but only if they still hash correctly."""
    read = get_payload(
        connection=connection,
        organization_id=organization_id,
        attempt_id=attempt_id,
        include_body=True,
    )
    failures = raw_payload_invariant_failures(read)

    payload = read.get("payload")
    if payload is None:
        # Not found, or another organization's. Scoping means those are the
        # same answer, which is the correct answer to give either way.
        return _result(
            attempt_id=str(attempt_id or "") or None,
            blocked_reasons=read["blocked_reasons"] or [BLOCK_NOT_FOUND],
            invariant_failures=failures,
        )

    verified = bool(read["hash_verified"])
    archived = payload.get("payload_status") == ARCHIVED

    provenance = {
        "attempt_id": payload.get("attempt_id"),
        "attempt_number": payload.get("attempt_number"),
        "collector_version": payload.get("collector_version"),
        "job_id": payload.get("job_id"),
        "source_id": payload.get("source_id"),
        "received_at": payload.get("received_at"),
        "organization_id": payload.get("organization_id"),
    }

    # Resolved by looking, not by reading the column back to itself.
    job_found = _job_exists(
        connection, read["payload"]["organization_id"], payload.get("job_id")
    )
    source_found = _source_known(payload.get("source_id"))

    blocked: list[str] = []
    if not verified:
        blocked.append(BLOCK_TAMPERED)
    if not payload.get("has_body"):
        blocked.append(BLOCK_NO_BODY)

    replayable = verified and bool(payload.get("has_body"))

    return _result(
        attempt_id=payload.get("attempt_id"),
        # Bytes are returned ONLY when the hash verified. A tampered payload
        # comes back with no body rather than with a warning beside it.
        replayable=replayable,
        hash_verified=verified,
        linked_job_found=job_found,
        linked_source_found=source_found,
        archived=archived,
        # Archive is a lifecycle state, not a deletion. An archived payload is
        # still readable.
        readable=True,
        body_base64=(
            payload.get("body_base64") if (replayable and include_body) else None
        ),
        payload_sha256=payload.get("payload_sha256"),
        payload_size_bytes=payload.get("payload_size_bytes"),
        media_type=payload.get("media_type"),
        encoding=payload.get("encoding"),
        response_status=payload.get("response_status"),
        safe_response_headers=payload.get("response_header_metadata") or {},
        retention_policy=payload.get("retention_policy"),
        retention_is_unknown=payload.get("retention_is_unknown"),
        provenance=provenance,
        blocked_reasons=blocked,
        invariant_failures=failures,
        readback_sha256=read.get("readback_sha256"),
        # Said plainly: replaying bytes is not evidence that they were ever
        # fetched from anywhere.
        replay_proves_storage_not_retrieval=True,
    )


def replay_invariant_failures(result: dict[str, Any]) -> list[str]:
    """Refuse a replay that handed back bytes it did not verify."""
    fails: list[str] = list(result.get("invariant_failures") or [])

    # THE invariant of this service.
    if result.get("body_base64") and not result.get("hash_verified"):
        fails.append("returned_a_body_without_verifying_the_hash")
    if result.get("replayable") and not result.get("hash_verified"):
        fails.append("reported_replayable_without_verifying_the_hash")
    if result.get("replayable") and result.get("blocked_reasons"):
        fails.append("replayable_alongside_blocked_reasons")
    if not result.get("replayable") and result.get("body_base64"):
        fails.append("returned_a_body_for_an_unreplayable_payload")
    if not result.get("replayable") and not result.get("blocked_reasons"):
        fails.append("not_replayable_without_naming_a_reason")

    for counter in (
        "collectors_invoked",
        "live_source_calls",
        "network_calls",
        "urls_fetched",
        "object_store_calls",
    ):
        if int(result.get(counter) or 0) != 0:
            fails.append(f"replay_counted:{counter}={result.get(counter)}")

    for claim in (
        "object_store_configured",
        "is_execution_proof",
        "source_monitoring_live",
    ):
        if result.get(claim):
            fails.append(f"replay_claimed:{claim}")

    # Provenance must be present whenever a payload was found.
    if result.get("payload_sha256") and not result.get("provenance"):
        fails.append("a_payload_was_found_without_reporting_its_provenance")

    provenance = result.get("provenance") or {}
    if provenance:
        for field in ("attempt_id", "job_id", "source_id"):
            if not str(provenance.get(field) or "").strip():
                fails.append(f"provenance_missing:{field}")

    digest = str(result.get("payload_sha256") or "")
    if digest and len(digest) != 64:
        fails.append(f"payload_hash_is_not_a_sha256_digest:{len(digest)}")

    # An archived payload must still be readable, or archive has become
    # deletion by accident.
    if result.get("archived") and not result.get("readable"):
        fails.append("an_archived_payload_was_reported_unreadable")

    return sorted(set(fails))
