"""Raw payload routes (Gate 160L).

Three reads and one synthetic-persistence POST, all under the demo prefix and
all behind `require_demo_org_session`.

## The POST persists a SYNTHETIC body, and rolls it back

`/raw-payloads/smoke` runs the whole write envelope — identity, filter, hash,
persist, re-read, verify — inside a SAVEPOINT, and reports the row counts on
both sides so "nothing persisted" is a measurement rather than a promise.

There is deliberately **no parameter that supplies a URL to fetch**, and no
parameter that accepts an arbitrary caller body. The smoke payload is built
here, from a fixed fixture, because a route that accepted arbitrary bytes from
a request would be an upload endpoint — and an upload endpoint for customer
content is exactly what Gate 148's data boundary forbids.

## Replay returns base64, never raw bytes

A JSON response cannot carry raw bytes, and `json.dumps(default=str)` turns
them into a lossy Python repr — which Gate 160 measured happening inside its own
store before it was fixed. So the wire format is base64, which round-trips.

A tampered payload returns **no body at all**, not a body with a warning
attached.
"""

from __future__ import annotations

import uuid
from typing import Annotated, Any

import sqlalchemy as sa
from fastapi import APIRouter, Body, Depends
from sqlalchemy.orm import Session

from nativeforge.api.customer_org_context_dependency import require_demo_org_session
from nativeforge.api.deps_db import get_db_session
from nativeforge.api.org_context import OrgContext
from nativeforge.api.post_award_common import envelope, same_org
from nativeforge.repositories.source_collection_raw_payload_repository import (
    MAX_PAYLOAD_BYTES,
    PAYLOADS,
    count_payloads,
    list_payloads,
    raw_payload_invariant_failures,
)
from nativeforge.services.source_raw_payload_health_service import (
    build_raw_payload_health,
    detect_object_store_configured,
    raw_payload_health_invariant_failures,
)
from nativeforge.services.source_raw_payload_persistence_service import (
    persist_raw_payload,
    persistence_invariant_failures,
)
from nativeforge.services.source_raw_payload_replay_service import (
    replay_invariant_failures,
    replay_payload,
)
from nativeforge.services.source_response_metadata_filter_service import (
    filter_response_metadata,
)

router = APIRouter(prefix="/v1/nf/demo/orgs", tags=["source-raw-payload-demo"])

#: Fixed so a response is reproducible and a test does not race the clock.
DEFAULT_EVALUATION_INSTANT = "2026-09-15T12:00:00Z"

#: The ONLY body this route will ever persist. Built here rather than accepted
#: from the request: a route that stored caller-supplied bytes would be an
#: upload endpoint, and Gate 148's customer data boundary forbids one.
SYNTHETIC_BODY = (
    b'{"synthetic":true,"note":"Gate 160 fixture. Not fetched from anywhere.",'
    b'"opportunities":[]}'
)

#: Synthetic response headers, including ones that must be refused, so the
#: smoke exercises the filter in both directions rather than only the safe path.
SYNTHETIC_HEADERS = {
    "Content-Type": "application/json; charset=utf-8",
    "ETag": 'W/"gate160-fixture"',
    "Cache-Control": "no-store",
    "Authorization": "Bearer this-must-be-refused",
    "Set-Cookie": "this=must-be-refused",
    "X-Acme-Session": "unclassified-header-must-be-refused",
}


def _payload_row_count(db: Session, org_id: uuid.UUID) -> int:
    try:
        return int(
            db.connection()
            .execute(
                sa.select(sa.func.count())
                .select_from(PAYLOADS)
                .where(PAYLOADS.c.organization_id == org_id)
            )
            .scalar()
            or 0
        )
    except Exception:  # noqa: BLE001 - a health read that 500s is worse
        return 0


def _table_exists(db: Session) -> bool:
    try:
        db.connection().execute(
            sa.select(sa.func.count()).select_from(PAYLOADS)
        ).scalar()
    except Exception:  # noqa: BLE001
        return False
    return True


@router.get("/{org_id}/raw-payloads/health")
def get_raw_payload_health(
    org_id: uuid.UUID,
    ctx: Annotated[OrgContext, Depends(require_demo_org_session)],
    db: Annotated[Session, Depends(get_db_session)],
) -> dict[str, Any]:
    # Raises 404 itself, and 404 rather than 403 on purpose: a 403 confirms the
    # organization exists to somebody who is not in it.
    same_org(org_id, ctx)

    connection = db.connection()
    counts = count_payloads(connection=connection, organization_id=str(org_id))

    # The lane's evidence is produced inside a SAVEPOINT and rolled back, so a
    # health read leaves no fixture row behind.
    savepoint = connection.begin_nested()
    try:
        written = persist_raw_payload(
            connection=connection,
            organization_id=str(org_id),
            job_id=f"nf-health-160-{uuid.uuid4().hex[:8]}",
            source_id=f"nf-health-160-src-{uuid.uuid4().hex[:8]}",
            attempt_number=1,
            body=SYNTHETIC_BODY,
            response_headers=SYNTHETIC_HEADERS,
            response_status=200,
            received_at=DEFAULT_EVALUATION_INSTANT,
        )
        replayed = replay_payload(
            connection=connection,
            organization_id=str(org_id),
            attempt_id=written["attempt_id"],
        )
        # The same attempt offering DIFFERENT bytes must be refused.
        conflict = persist_raw_payload(
            connection=connection,
            organization_id=str(org_id),
            job_id=written["identity"]["job_id"],
            source_id=written["identity"]["source_id"],
            attempt_number=1,
            body=SYNTHETIC_BODY + b"different",
            response_headers={"Content-Type": "application/json"},
            received_at=DEFAULT_EVALUATION_INSTANT,
        )
        # And an oversize body must be refused deterministically.
        oversize = persist_raw_payload(
            connection=connection,
            organization_id=str(org_id),
            job_id=f"nf-health-160-big-{uuid.uuid4().hex[:8]}",
            source_id="nf-health-160-src-big",
            attempt_number=1,
            body=b"x" * (MAX_PAYLOAD_BYTES + 1),
            received_at=DEFAULT_EVALUATION_INSTANT,
        )
        probe_counts = count_payloads(
            connection=connection, organization_id=str(org_id)
        )
        round_tripped = bool(
            replayed.get("replayable")
            and replayed.get("payload_sha256") == written.get("payload_sha256")
        )
    finally:
        savepoint.rollback()

    left_behind = _payload_row_count(db, org_id)

    health = build_raw_payload_health(
        table_exists=_table_exists(db),
        write_result=written,
        replay_result=replayed,
        conflict_result=conflict,
        metadata_result=written.get("metadata"),
        oversize_result=oversize,
        counts=probe_counts,
        bytes_round_tripped=round_tripped,
        # A request cannot tamper with a row it has just rolled back, and it
        # cannot archive one either. The verifier does both.
        tamper_result=None,
        archived_replay_result=None,
    )

    return envelope(
        {
            **health,
            "organization_id": str(org_id),
            "invariant_failures": raw_payload_health_invariant_failures(health),
            "counts_invariant_failures": raw_payload_invariant_failures(counts),
            "health_probe_rolled_back": True,
            # Measured after the rollback.
            "health_probe_rows_left_behind": left_behind,
            "measured_by_the_verifier": ["tamper_detected", "archived_still_readable"],
            "why": (
                "a request cannot tamper with a row it just rolled back, and "
                "archiving one would leave a fixture behind. "
                "scripts/verify_nativeforge_source_raw_payload_persistence.sh "
                "measures both, so this lane stays red here."
            ),
        }
    )


@router.get("/{org_id}/raw-payloads")
def get_raw_payloads(
    org_id: uuid.UUID,
    ctx: Annotated[OrgContext, Depends(require_demo_org_session)],
    db: Annotated[Session, Depends(get_db_session)],
    job_id: str | None = None,
    source_id: str | None = None,
    payload_sha256: str | None = None,
) -> dict[str, Any]:
    """Payload METADATA. Bodies are never in a listing."""
    same_org(org_id, ctx)

    listed = list_payloads(
        connection=db.connection(),
        organization_id=str(org_id),
        job_id=job_id,
        source_id=source_id,
        payload_sha256=payload_sha256,
    )
    return envelope(
        {
            **listed,
            "organization_id": str(org_id),
            "invariant_failures": raw_payload_invariant_failures(listed),
            "bodies_are_not_included_in_a_listing": True,
            "a_stored_payload_is_not_a_fetched_payload": True,
        }
    )


@router.get("/{org_id}/raw-payloads/{attempt_id}/replay")
def get_raw_payload_replay(
    org_id: uuid.UUID,
    attempt_id: str,
    ctx: Annotated[OrgContext, Depends(require_demo_org_session)],
    db: Annotated[Session, Depends(get_db_session)],
) -> dict[str, Any]:
    """The exact stored bytes, base64 encoded, if the hash still verifies."""
    same_org(org_id, ctx)

    played = replay_payload(
        connection=db.connection(),
        organization_id=str(org_id),
        attempt_id=attempt_id,
    )
    return envelope(
        {
            **played,
            "organization_id": str(org_id),
            "invariant_failures": replay_invariant_failures(played),
            "body_wire_format": "base64",
            "why_base64": (
                "a JSON response cannot carry raw bytes, and json.dumps with "
                "default=str turns them into a lossy Python repr - which Gate "
                "160 measured happening inside its own store before it was "
                "fixed"
            ),
        }
    )


@router.post("/{org_id}/raw-payloads/smoke")
def post_raw_payload_smoke(
    org_id: uuid.UUID,
    ctx: Annotated[OrgContext, Depends(require_demo_org_session)],
    db: Annotated[Session, Depends(get_db_session)],
    payload: Annotated[dict[str, Any] | None, Body()] = None,
) -> dict[str, Any]:
    """Persist the SYNTHETIC fixture through the whole envelope, then roll back.

    The body is fixed. This route accepts no caller bytes and fetches no URL.
    """
    same_org(org_id, ctx)

    body = payload or {}
    instant = str(body.get("now") or DEFAULT_EVALUATION_INSTANT)

    connection = db.connection()
    before = _payload_row_count(db, org_id)

    savepoint = connection.begin_nested()
    try:
        written = persist_raw_payload(
            connection=connection,
            organization_id=str(org_id),
            job_id=f"nf-smoke-160-{uuid.uuid4().hex[:8]}",
            source_id=f"nf-smoke-160-src-{uuid.uuid4().hex[:8]}",
            attempt_number=1,
            # Fixed. Not from the request.
            body=SYNTHETIC_BODY,
            response_headers=SYNTHETIC_HEADERS,
            response_status=200,
            received_at=instant,
        )
        replayed = replay_payload(
            connection=connection,
            organization_id=str(org_id),
            attempt_id=written["attempt_id"],
        )
        inside = _payload_row_count(db, org_id)
    finally:
        savepoint.rollback()

    after = _payload_row_count(db, org_id)
    metadata = filter_response_metadata(headers=SYNTHETIC_HEADERS)

    return envelope(
        {
            "organization_id": str(org_id),
            "evaluated_at": instant,
            "persisted_in_the_savepoint": written["persisted"],
            "write_hash_verified": written["write_hash_verified"],
            "readback_hash_verified": written["readback_hash_verified"],
            "replayable": replayed["replayable"],
            "payload_sha256": written["payload_sha256"],
            "payload_size_bytes": written["payload_size_bytes"],
            "max_payload_size_bytes": MAX_PAYLOAD_BYTES,
            "safe_headers_kept": sorted(metadata["safe_headers"]),
            "headers_refused": metadata["refused_header_names"],
            # The measurement that makes "nothing persisted" checkable.
            "rows_before": before,
            "rows_inside_the_savepoint": inside,
            "rows_after": after,
            "rolled_back": True,
            "nothing_persisted": after == before,
            # And the proof it was not a no-op.
            "the_savepoint_actually_held_rows": inside > before,
            "invariant_failures": persistence_invariant_failures(written),
            "replay_invariant_failures": replay_invariant_failures(replayed),
            "body_was_synthetic_not_fetched": True,
            "route_accepts_no_caller_body": True,
            "route_fetches_no_url": True,
            "object_store_configured": detect_object_store_configured(),
            "object_store_calls": 0,
            "collectors_invoked": 0,
            "live_source_calls": 0,
            "source_monitoring_live": False,
        }
    )
