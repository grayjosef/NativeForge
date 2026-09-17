"""Collector execution routes (Gate 161L).

Two reads and one hermetic smoke, all under the demo prefix and all behind
`require_demo_org_session`.

## There is no parameter that takes a URL

Not an optional one, not a validated one, not an allowlisted one. The smoke
request is built here from a fixture defined in this module, and the transport
is a `HermeticTransportRegistry` constructed per request with that one URL
registered.

That is the whole SSRF answer, and it is structural rather than defensive: a
route cannot be tricked into fetching an internal address by a caller who
cannot name an address. Filtering a caller-supplied URL would mean writing a
filter that has to be right every time, against an attacker who only has to be
right once — and the campaign's own record on "does this text appear" checks is
thirteen defects long.

The transport registry is also per-request rather than module-level. A shared
one would be state a caller could accumulate into.

## The smoke runs inside a SAVEPOINT and rolls back

It enqueues a real job, executes against the fixture, persists the bytes, and
rolls the lot back. Row counts on both sides, so "nothing persisted" is a
measurement rather than a promise.

The job is created rather than invented because the proof requires
`provenance_resolves` — attempt → job → source, each resolved by looking. A
smoke naming a job nobody enqueued satisfies six of seven requirements and never
exercises the seventh, which is what this route did until the proof refused it.

The report includes that proof, which says `proves_a_source_responded: false` —
because a fixture answered.

## A refused execution is still a 200

The route reports what the envelope decided. Turning a refusal into a 4xx would
make "the policy refused this" indistinguishable from "you asked wrongly", and
an operator reading the refusal reason is the point of the endpoint.
"""

from __future__ import annotations

import uuid
from typing import Annotated, Any

import sqlalchemy as sa
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from nativeforge.api.customer_org_context_dependency import require_demo_org_session
from nativeforge.api.deps_db import get_db_session
from nativeforge.api.org_context import OrgContext
from nativeforge.api.post_award_common import envelope, same_org
from nativeforge.repositories.source_collection_execution_attempt_repository import (
    ATTEMPTS,
    count_attempts,
    get_attempt,
    list_attempts,
)
from nativeforge.repositories.source_collection_job_repository import enqueue_job
from nativeforge.services.hermetic_source_transport_service import (
    HermeticTransportRegistry,
)
from nativeforge.services.source_collection_execution_retry_service import (
    evaluate_execution_retry,
    execution_retry_invariant_failures,
)
from nativeforge.services.source_collection_transport_service import (
    HERMETIC,
    describe_boundary,
)
from nativeforge.services.source_collector_execution_health_service import (
    build_execution_health,
    execution_health_invariant_failures,
)
from nativeforge.services.source_collector_execution_service import (
    execute_collection,
    execution_invariant_failures,
)

router = APIRouter(prefix="/v1/nf/demo/orgs", tags=["source-collector-execution-demo"])

#: Fixed so a response is reproducible and a test does not race the clock.
DEFAULT_EVALUATION_INSTANT = "2026-09-16T12:00:00Z"

#: The ONLY URL this route will ever construct a request for, and it resolves
#: nowhere: `.invalid` is reserved by RFC 2606 precisely so it cannot exist.
#:
#: It is a constant in this module and not a parameter, not a default, and not
#: an allowlist entry a caller can select from. A route that cannot be told an
#: address cannot be pointed at one.
SMOKE_URL = "https://fixtures.invalid/nf161/smoke"

#: Its source id carries the fixture prefix the worker's predicate requires,
#: and the approved-source registry has never heard of it.
SMOKE_SOURCE_ID = "nf161.fixture.smoke"

#: The bytes the fixture answers with. Built here, never accepted from a
#: request: a route that stored caller-supplied bytes would be an upload
#: endpoint, and Gate 148's customer data boundary forbids one.
SMOKE_BODY = (
    b'{"synthetic":true,"note":"Gate 161 fixture. Nothing was contacted.",'
    b'"opportunities":[]}'
)


def _build_smoke_transport() -> HermeticTransportRegistry:
    """A registry holding exactly one URL, built fresh for each request.

    Per-request rather than module-level: a shared registry would be state a
    caller could accumulate into across requests.
    """
    registry = HermeticTransportRegistry()
    registry.register_ok(SMOKE_URL, SMOKE_BODY, etag='W/"gate161-fixture"')
    return registry


def _attempt_row_count(db: Session, org_id: uuid.UUID) -> int:
    try:
        return int(
            db.connection()
            .execute(
                sa.select(sa.func.count())
                .select_from(ATTEMPTS)
                .where(ATTEMPTS.c.organization_id == org_id)
            )
            .scalar()
            or 0
        )
    except Exception:  # noqa: BLE001 - a health read that 500s is worse
        return 0


@router.get("/{org_id}/collector-execution/health")
def get_collector_execution_health(
    org_id: uuid.UUID,
    ctx: Annotated[OrgContext, Depends(require_demo_org_session)],
    db: Annotated[Session, Depends(get_db_session)],
) -> dict[str, Any]:
    # Raises 404 itself, and 404 rather than 403 on purpose: a 403 confirms the
    # organization exists to somebody who is not in it.
    same_org(org_id, ctx)

    connection = db.connection()
    health = build_execution_health(
        connection=connection, organization_id=str(org_id)
    )
    boundary = describe_boundary()

    return envelope(
        {
            "health": health,
            "invariant_failures": execution_health_invariant_failures(health),
            "transport_boundary": boundary,
            # Repeated at the top level because a reader who takes only these
            # four fields must still get the right answer.
            "execution_envelope_ready": health["execution_envelope_ready"],
            "live_transport_available": health["live_transport_available"],
            "approved_source_count": health["approved_source_count"],
            "source_monitoring_live": False,
        }
    )


@router.get("/{org_id}/collector-execution/attempts")
def list_collector_execution_attempts(
    org_id: uuid.UUID,
    ctx: Annotated[OrgContext, Depends(require_demo_org_session)],
    db: Annotated[Session, Depends(get_db_session)],
    limit: int = 50,
) -> dict[str, Any]:
    same_org(org_id, ctx)

    connection = db.connection()
    listed = list_attempts(
        connection=connection,
        organization_id=str(org_id),
        limit=max(1, min(int(limit), 200)),
    )
    counts = count_attempts(connection=connection, organization_id=str(org_id))

    # Metadata only. The attempt table holds no body by design - it points at
    # Gate 160's bytes by hash - so there is nothing here to strip.
    return envelope(
        {
            "attempts": listed.get("attempts") or [],
            "counts": counts,
            "blocked_reasons": listed.get("blocked_reasons") or [],
            "holds_no_response_body": True,
            "holds_no_request_url": (
                "a sha256 fingerprint is stored instead, as Gate 160 settled"
            ),
            "live_attempts": int(counts.get("live_attempts") or 0),
            "source_monitoring_live": False,
        }
    )


@router.get("/{org_id}/collector-execution/attempts/{attempt_id}")
def get_collector_execution_attempt(
    org_id: uuid.UUID,
    attempt_id: str,
    ctx: Annotated[OrgContext, Depends(require_demo_org_session)],
    db: Annotated[Session, Depends(get_db_session)],
) -> dict[str, Any]:
    same_org(org_id, ctx)

    found = get_attempt(
        connection=db.connection(),
        organization_id=str(org_id),
        attempt_id=str(attempt_id),
    )
    return envelope(
        {
            "attempt": found.get("attempt"),
            "found": found.get("attempt") is not None,
            "blocked_reasons": found.get("blocked_reasons") or [],
            "source_monitoring_live": False,
        }
    )


@router.post("/{org_id}/collector-execution/smoke")
def run_collector_execution_smoke(
    org_id: uuid.UUID,
    ctx: Annotated[OrgContext, Depends(require_demo_org_session)],
    db: Annotated[Session, Depends(get_db_session)],
) -> dict[str, Any]:
    """Run the envelope against the one registered fixture, then roll it back.

    Takes NO request body. There is nothing a caller could put in one that this
    route would use, and accepting one would invite the belief that there is.
    """
    same_org(org_id, ctx)

    connection = db.connection()
    before = _attempt_row_count(db, org_id)

    job_id = f"nf-smoke-161-{uuid.uuid4().hex[:8]}"

    savepoint = connection.begin_nested()
    try:
        # The job is REAL, and it is created here rather than invented.
        #
        # `build_execution_proof` requires `provenance_resolves`: attempt ->
        # job -> source, each resolved by looking. A smoke that names a job
        # nobody enqueued can satisfy six of the seven requirements and never
        # test the seventh - which is exactly what this route did until the
        # proof refused it.
        enqueued = enqueue_job(
            connection=connection,
            organization_id=str(org_id),
            job_id=job_id,
            idempotency_key=job_id,
            source_id=SMOKE_SOURCE_ID,
            schedule_key="nf161-smoke",
            scheduled_for=DEFAULT_EVALUATION_INSTANT,
            now=DEFAULT_EVALUATION_INSTANT,
        )

        report = execute_collection(
            connection=connection,
            organization_id=str(org_id),
            job_id=job_id,
            source_definition={
                "source_id": SMOKE_SOURCE_ID,
                "endpoint": SMOKE_URL,
                "method": "GET",
            },
            transport=_build_smoke_transport().transport,
            transport_kind=HERMETIC,
            now=DEFAULT_EVALUATION_INSTANT,
            is_synthetic_fixture=True,
        )
        inside = _attempt_row_count(db, org_id)

        # What the retry policy would say about this outcome. Decided, never
        # acted on: this route schedules nothing.
        retry = evaluate_execution_retry(
            outcome=(report.get("transport") or {}).get("outcome"),
            http_status=report.get("http_status"),
            response_headers=(report.get("transport") or {}).get(
                "response_headers"
            ),
            refusal_reasons=report.get("blocked_reasons"),
            attempt_count=0,
            now=DEFAULT_EVALUATION_INSTANT,
        )
    finally:
        # Unconditional. A smoke that left a row behind on an error path would
        # be a write endpoint that only sometimes writes.
        savepoint.rollback()

    after = _attempt_row_count(db, org_id)
    proof = report.get("proof") or {}

    return envelope(
        {
            "smoke": {
                "execution_status": report["execution_status"],
                "refusal_reason": report["refusal_reason"],
                "request_prepared": report["request_prepared"],
                "transport_invoked": report["transport_invoked"],
                "response_received": report["response_received"],
                "http_status": report["http_status"],
                "bytes_received": report["bytes_received"],
                "raw_payload_sha256": report["raw_payload_sha256"],
                "execution_proof_available": report["execution_proof_available"],
                "blocked_reasons": report["blocked_reasons"],
            },
            "proof": proof,
            # WHICH requirement went missing, not merely that one did. A proof
            # reported absent without naming its gap is a fault report with the
            # fault left out.
            "proof_requirements_not_met": proof.get("requirements_not_met") or [],
            "job_was_enqueued": bool(enqueued.get("created")),
            "retry_decision": retry,
            "invariant_failures": sorted(
                set(
                    execution_invariant_failures(report)
                    + execution_retry_invariant_failures(retry)
                )
            ),
            # Measured on both sides rather than promised.
            "attempt_rows_before": before,
            "attempt_rows_during": inside,
            "attempt_rows_after": after,
            "rolled_back": after == before,
            # ---- what this did NOT do -----------------------------------
            "caller_can_supply_a_url": False,
            "caller_can_supply_a_body": False,
            "url_came_from": "a constant in this module",
            "transport_kind": HERMETIC,
            "live_source_call": False,
            "network_calls": 0,
            "dns_resolved": False,
            "collectors_invoked": 0,
            "approved_source_count": 0,
            "source_monitoring_live": False,
            "proves_a_source_responded": bool(
                proof.get("proves_a_source_responded")
            ),
            "what_this_proves": (
                "the execution envelope composes end to end against a "
                "registered fixture. Nothing was contacted, and a hermetic "
                "proof is not a source having answered."
            ),
        }
    )
