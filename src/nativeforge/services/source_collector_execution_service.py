"""The collector execution envelope (Gate 161B).

One pass, in this order:

```text
1  attempt identity          Gate 160B
2  execution policy          Gate 161D, composing Gate 94B's guard
3  request construction      Gate 161E, from the source definition
4  transport dispatch        Gate 161C, through the boundary
5  raw payload persistence   Gate 160G, exact bytes, hash verified twice
6  execution proof           Gate 161H, seven requirements
7  attempt record            Gate 161G, written for EVERY outcome
```

Step 7 runs whatever happened. A refusal at step 2 and a timeout at step 4 both
produce no payload, and without an attempt row there would be no record they
occurred — which is the fact an operator needs when a source stops working.

## Malformed bytes are still evidence

161J: parsing is not a prerequisite for preserving a response. A 200 whose body
no parser accepts still reaches Gate 160 intact, still hashes, and still counts
as `response_received`. The execution succeeded; the parse is a later gate's
problem, and conflating them would discard the only copy of what arrived.

## Nothing here imports a network module

The transport is injected. This module has no `httpx`, no `socket`, and no
parameter that takes a URL from a caller — the request is built from the source
definition, which is the difference between "collect this source" and "fetch
this URL".
"""

from __future__ import annotations

import json
from typing import Any

from nativeforge.repositories.source_collection_execution_attempt_repository import (
    BLOCK_DUPLICATE,
    BLOCK_LIVE,
    BLOCK_REAL_ORG,
    REFUSED_BY_POLICY,
    REQUEST_BUILD_FAILED,
    RESPONSE_PERSISTED,
    RESPONSE_RECEIVED,
    TRANSPORT_FAILED,
    TRANSPORT_REFUSED,
    attempt_invariant_failures,
    record_attempt,
)
from nativeforge.services.source_collection_attempt_identity_service import (
    attempt_identity_invariant_failures,
    build_attempt_identity,
)
from nativeforge.services.source_collection_execution_policy_service import (
    build_execution_policy,
    execution_policy_invariant_failures,
)
from nativeforge.services.source_collection_execution_proof_service import (
    build_execution_proof,
    execution_proof_invariant_failures,
)
from nativeforge.services.source_collection_request_builder_service import (
    build_source_request,
    request_builder_invariant_failures,
)
from nativeforge.services.source_collection_transport_service import (
    HERMETIC,
    LIVE,
    OUTCOME_CONNECTION_FAILED,
    OUTCOME_MALFORMED,
    OUTCOME_OK,
    OUTCOME_TIMEOUT,
    execute_request,
    transport_invariant_failures,
)
from nativeforge.services.source_raw_payload_persistence_service import (
    persist_raw_payload,
    persistence_invariant_failures,
)
from nativeforge.services.source_raw_payload_replay_service import (
    replay_invariant_failures,
    replay_payload,
)

SCHEMA_VERSION = "nf_source_collector_execution_v1"

CONTROLLED_SCOPE = "controlled_dev_demo"

COMPOSES = (
    "source_collection_attempt_identity_service.build_attempt_identity",
    "source_collection_execution_policy_service.build_execution_policy",
    "source_collection_request_builder_service.build_source_request",
    "source_collection_transport_service.execute_request",
    "source_raw_payload_persistence_service.persist_raw_payload",
    "source_raw_payload_replay_service.replay_payload",
    "source_collection_execution_proof_service.build_execution_proof",
    "source_collection_execution_attempt_repository.record_attempt",
)

#: The only reasons an execution may finish without an attempt row.
#:
#: Each is the attempt table refusing a write ON PURPOSE, and the refusal is a
#: better record than the row:
#:
#: - a duplicate means the row already exists, written by an earlier pass;
#: - a live attempt is not a thing this database can hold while Gate 161 stands
#:   (migration 0047, `CHECK transport_kind = 'hermetic'`), so the named refusal
#:   IS the record that someone asked;
#: - the real organization is refused by name, and writing rows against it is
#:   exactly what the standing authorization forbids.
#:
#: Imported as constants rather than spelled out, so a renamed reason breaks the
#: import instead of quietly widening the exemption.
ROW_REFUSED_ON_PURPOSE: frozenset[str] = frozenset(
    {BLOCK_DUPLICATE, BLOCK_LIVE, BLOCK_REAL_ORG}
)

#: Transport outcome -> the refusal reason recorded on the attempt.
OUTCOME_TO_REFUSAL: dict[str, str] = {
    OUTCOME_TIMEOUT: "transport_timeout",
    OUTCOME_CONNECTION_FAILED: "transport_connection_failed",
}


def _json_safe(value: Any) -> Any:
    return json.loads(json.dumps(value, default=str, sort_keys=True))


def _report(**fields: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "scope": CONTROLLED_SCOPE,
        "execution_attempt_id": None,
        "job_id": None,
        "source_id": None,
        "collector_version": None,
        "request_prepared": False,
        "transport_invoked": False,
        "response_received": False,
        "raw_payload_id": None,
        "raw_payload_sha256": None,
        "http_status": None,
        "bytes_received": 0,
        "execution_status": None,
        "refusal_reason": "none",
        "execution_proof_available": False,
        "attempt_recorded": False,
        "blocked_reasons": [],
        "invariant_failures": [],
        "composes": list(COMPOSES),
        # Constants. A hermetic execution contacted nothing.
        "transport_kind": HERMETIC,
        "live_source_call": False,
        "live_transport_enabled": False,
        "collectors_invoked": 0,
        "live_source_calls": 0,
        "network_calls": 0,
        "approved_source_count": 0,
        "source_monitoring_live": False,
    }
    base.update(fields)
    base["blocked_reasons"] = sorted(set(base["blocked_reasons"] or []))
    base["invariant_failures"] = sorted(set(base["invariant_failures"] or []))
    return _json_safe(base)


def execute_collection(
    *,
    connection: Any = None,
    organization_id: Any = None,
    job_id: Any = None,
    source_definition: dict[str, Any] | None = None,
    attempt_number: Any = 1,
    collector_version: Any = None,
    transport: Any = None,
    transport_kind: str = HERMETIC,
    now: Any = None,
    user_agent: Any = None,
    is_synthetic_fixture: bool = False,
    scope: str = CONTROLLED_SCOPE,
    policy_inputs: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """One execution pass. Records an attempt whatever happens."""
    definition = dict(source_definition or {})
    source_id = definition.get("source_id")
    failures: list[str] = []

    # ---- 1. identity ------------------------------------------------------
    identity_kwargs: dict[str, Any] = {
        "job_id": job_id,
        "source_id": source_id,
        "attempt_number": attempt_number,
    }
    if collector_version is not None:
        identity_kwargs["collector_version"] = collector_version
    identity = build_attempt_identity(**identity_kwargs)
    failures.extend(attempt_identity_invariant_failures(identity))

    if not identity["usable"]:
        return _report(
            job_id=job_id,
            source_id=source_id,
            blocked_reasons=identity["blocked_reasons"],
            # This return predates `_finish`, so it carries its own failures.
            invariant_failures=failures,
            execution_status=REFUSED_BY_POLICY,
            refusal_reason="unknown",
        )

    attempt_id = identity["attempt_id"]
    common = {
        "execution_attempt_id": attempt_id,
        "job_id": identity["job_id"],
        "source_id": identity["source_id"],
        "collector_version": identity["collector_version"],
        "transport_kind": transport_kind,
    }

    # What the attempt table itself refused or noted. A duplicate lands here,
    # and `execution_invariant_failures` needs to see it.
    record_blocked: list[str] = []

    def _record(**kwargs: Any) -> dict[str, Any]:
        """Write the attempt row. Runs on every path, including refusals."""
        written = record_attempt(
            connection=connection,
            organization_id=organization_id,
            attempt_id=attempt_id,
            attempt_number=identity["attempt_number"],
            collector_version=identity["collector_version"],
            job_id=identity["job_id"],
            source_id=identity["source_id"],
            started_at=now,
            completed_at=now,
            transport_kind=transport_kind,
            **kwargs,
        )
        failures.extend(attempt_invariant_failures(written))
        record_blocked.extend(written.get("blocked_reasons") or [])
        return written

    def _finish(**fields: Any) -> dict[str, Any]:
        """Every return after identity. One place that assembles a report."""
        fields["blocked_reasons"] = list(fields.get("blocked_reasons") or []) + (
            record_blocked
        )
        fields["invariant_failures"] = list(
            fields.get("invariant_failures") or []
        ) + failures
        return _report(**fields)

    # ---- 2. policy --------------------------------------------------------
    policy = build_execution_policy(
        source_id=source_id,
        organization_id=organization_id,
        is_synthetic_fixture=is_synthetic_fixture,
        scope=scope,
        transport_kind=transport_kind,
        target_url=definition.get("endpoint"),
        **(policy_inputs or {}),
    )
    failures.extend(execution_policy_invariant_failures(policy))

    if not policy["execution_allowed"]:
        recorded = _record(
            execution_status=REFUSED_BY_POLICY,
            refusal_reason=_policy_refusal_reason(policy),
            blocked_reasons=policy["refusal_reasons"],
        )
        return _finish(
            **common,
            blocked_reasons=policy["refusal_reasons"],
            execution_status=REFUSED_BY_POLICY,
            refusal_reason=_policy_refusal_reason(policy),
            attempt_recorded=recorded["recorded"],
            policy=policy,
        )

    # ---- 3. request -------------------------------------------------------
    built = build_source_request(
        source_definition=definition, user_agent=user_agent
    )
    failures.extend(request_builder_invariant_failures(built))

    if not built["usable"]:
        recorded = _record(
            execution_status=REQUEST_BUILD_FAILED,
            refusal_reason="request_build_refused",
            blocked_reasons=built["blocked_reasons"],
        )
        return _finish(
            **common,
            blocked_reasons=built["blocked_reasons"],
            execution_status=REQUEST_BUILD_FAILED,
            refusal_reason="request_build_refused",
            attempt_recorded=recorded["recorded"],
            policy=policy,
            request=built.get("request"),
        )

    request = built["transport_request"]
    fingerprint = (built.get("request") or {}).get("url_fingerprint")

    # ---- 4. transport -----------------------------------------------------
    dispatch = execute_request(
        request=request,
        transport_kind=transport_kind,
        transport=transport,
        policy=policy,
    )
    failures.extend(transport_invariant_failures(dispatch))

    if not dispatch["dispatched"]:
        recorded = _record(
            execution_status=TRANSPORT_REFUSED,
            refusal_reason=_transport_refusal_reason(dispatch),
            blocked_reasons=dispatch["blocked_reasons"],
            request_url_fingerprint=fingerprint,
            request_method=built["method"],
        )
        return _finish(
            **common,
            request_prepared=True,
            blocked_reasons=dispatch["blocked_reasons"],
            execution_status=TRANSPORT_REFUSED,
            refusal_reason=_transport_refusal_reason(dispatch),
            attempt_recorded=recorded["recorded"],
            policy=policy,
            request=built.get("request"),
            transport=dispatch,
        )

    outcome = dispatch["outcome"]
    # A malformed body IS a response. Parsing is a later concern, and treating
    # it as a failure here would discard the only copy of what arrived.
    received = outcome in (OUTCOME_OK, OUTCOME_MALFORMED)

    if not received:
        recorded = _record(
            execution_status=TRANSPORT_FAILED,
            refusal_reason=OUTCOME_TO_REFUSAL.get(outcome, "unknown"),
            blocked_reasons=[f"transport_outcome:{outcome}"],
            transport_outcome=outcome,
            request_url_fingerprint=fingerprint,
            request_method=built["method"],
        )
        return _finish(
            **common,
            request_prepared=True,
            transport_invoked=True,
            execution_status=TRANSPORT_FAILED,
            refusal_reason=OUTCOME_TO_REFUSAL.get(outcome, "unknown"),
            blocked_reasons=[f"transport_outcome:{outcome}"],
            attempt_recorded=recorded["recorded"],
            http_status=dispatch["status_code"],
            transport_outcome=outcome,
            policy=policy,
            request=built.get("request"),
            transport=dispatch,
        )

    body = dispatch.get("body_bytes") or b""

    # ---- 5. persist the exact bytes --------------------------------------
    stored = persist_raw_payload(
        connection=connection,
        organization_id=organization_id,
        job_id=identity["job_id"],
        source_id=identity["source_id"],
        attempt_number=identity["attempt_number"],
        collector_version=identity["collector_version"],
        body=body,
        response_headers=dispatch.get("response_headers"),
        response_status=dispatch["status_code"],
        source_url=request.url,
        received_at=now,
    )
    failures.extend(persistence_invariant_failures(stored))

    persisted = bool(stored["persisted"] or stored["deduplicated"])

    # ---- 6. proof ---------------------------------------------------------
    played = (
        replay_payload(
            connection=connection,
            organization_id=organization_id,
            attempt_id=attempt_id,
        )
        if persisted
        else {}
    )
    if played:
        failures.extend(replay_invariant_failures(played))

    proof = build_execution_proof(
        attempt={
            "attempt_id": attempt_id,
            "job_id": identity["job_id"],
            "source_id": identity["source_id"],
            "transport_kind": transport_kind,
            "raw_payload_persisted": persisted,
            "raw_payload_sha256": stored.get("payload_sha256"),
            "bytes_received": dispatch["bytes_received"],
        },
        payload=stored,
        replay=played,
        policy=policy,
        transport_result=dispatch,
    )
    failures.extend(execution_proof_invariant_failures(proof))

    # ---- 7. the attempt row ----------------------------------------------
    recorded = _record(
        execution_status=RESPONSE_PERSISTED if persisted else RESPONSE_RECEIVED,
        refusal_reason="none",
        transport_outcome=outcome,
        http_status=dispatch["status_code"],
        bytes_received=dispatch["bytes_received"],
        request_url_fingerprint=fingerprint,
        request_method=built["method"],
        raw_payload_sha256=stored.get("payload_sha256"),
        raw_payload_persisted=persisted,
        execution_proof_available=bool(proof["execution_proof_available"]),
        blocked_reasons=stored.get("blocked_reasons") or [],
    )

    return _finish(
        **common,
        request_prepared=True,
        transport_invoked=True,
        response_received=True,
        raw_payload_id=attempt_id,
        raw_payload_sha256=stored.get("payload_sha256"),
        http_status=dispatch["status_code"],
        bytes_received=dispatch["bytes_received"],
        execution_status=RESPONSE_PERSISTED if persisted else RESPONSE_RECEIVED,
        refusal_reason="none",
        execution_proof_available=bool(proof["execution_proof_available"]),
        attempt_recorded=recorded["recorded"],
        transport_outcome=outcome,
        response_was_malformed=outcome == OUTCOME_MALFORMED,
        policy=policy,
        request=built.get("request"),
        transport=dispatch,
        payload=stored,
        proof=proof,
    )


def _policy_refusal_reason(policy: dict[str, Any]) -> str:
    """Map the policy's refusal onto the attempt table's vocabulary."""
    reasons = set(policy.get("refusal_reasons") or [])
    if any("synthetic_fixture" in reason for reason in reasons):
        return "not_a_synthetic_fixture"
    if any("scope" in reason for reason in reasons):
        return "scope_not_permitted"
    if any("live_network_guard" in reason for reason in reasons):
        return "live_transport_not_permitted"
    if any("real_organization" in reason for reason in reasons):
        return "permanent_worker_failure"
    return "unknown"


def _transport_refusal_reason(dispatch: dict[str, Any]) -> str:
    reasons = set(dispatch.get("blocked_reasons") or [])
    if any("no_implementation" in reason for reason in reasons):
        return "live_transport_not_implemented"
    if any("not_dispatchable" in reason for reason in reasons):
        return "live_transport_not_permitted"
    if any("exceeds_max_bytes" in reason for reason in reasons):
        return "response_too_large"
    if any("policy_refused" in reason or "policy" in reason for reason in reasons):
        return "live_transport_not_permitted"
    return "unknown"


def execution_invariant_failures(report: dict[str, Any]) -> list[str]:
    """Refuse an execution that claims a live call, or contradicts itself."""
    fails: list[str] = list(report.get("invariant_failures") or [])

    for counter in (
        "collectors_invoked",
        "live_source_calls",
        "network_calls",
        "approved_source_count",
    ):
        if int(report.get(counter) or 0) != 0:
            fails.append(f"execution_counted:{counter}={report.get(counter)}")

    for claim in (
        "live_source_call",
        "live_transport_enabled",
        "source_monitoring_live",
    ):
        if report.get(claim):
            fails.append(f"execution_claimed:{claim}")

    # What was REQUESTED is not what RAN. A caller asking for `live` and being
    # refused is this envelope working, so the invariant is about the
    # invocation. Flagging the request as a violation would make a correct
    # refusal indistinguishable from a breach, and the one check that must stay
    # readable is this one.
    kind = report.get("transport_kind")
    if report.get("transport_invoked") and kind != HERMETIC:
        fails.append(f"a_non_hermetic_transport_was_invoked:{kind}")
    if kind == LIVE and report.get("transport_invoked"):
        fails.append("a_live_transport_was_invoked")
    if kind not in (HERMETIC, LIVE):
        fails.append(f"transport_kind_outside_the_vocabulary:{kind}")

    # Ordering invariants: each stage requires the one before it.
    if report.get("response_received") and not report.get("transport_invoked"):
        fails.append("a_response_without_a_transport_invocation")
    if report.get("transport_invoked") and not report.get("request_prepared"):
        fails.append("a_transport_invocation_without_a_prepared_request")
    if report.get("raw_payload_sha256") and not report.get("response_received"):
        fails.append("a_payload_without_a_response")

    # A proof requires a response and a payload.
    if report.get("execution_proof_available"):
        if not report.get("response_received"):
            fails.append("a_proof_without_a_response")
        if not report.get("raw_payload_sha256"):
            fails.append("a_proof_without_a_persisted_payload")

    # EVERY outcome gets an attempt row. That is the point of the table - a
    # refusal and a timeout both produce no payload, and without a row there is
    # no record they happened.
    #
    # Three exceptions, each because the attempt table itself refused the write
    # and that refusal is a stronger record than the row would have been. They
    # are matched by EXACT reason, never by substring: a loose match here would
    # eventually excuse a missing row for a reason nobody intended.
    if report.get("execution_status") and not report.get("attempt_recorded"):
        reasons = set(report.get("blocked_reasons") or [])
        if not (reasons & ROW_REFUSED_ON_PURPOSE):
            fails.append("an_execution_finished_without_recording_an_attempt")

    return sorted(set(fails))
