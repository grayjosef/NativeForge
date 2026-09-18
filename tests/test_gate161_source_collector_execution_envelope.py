"""Gate 161: the collector execution envelope.

The tests worth having here are the ones that could fail. Three kinds:

1. **Falsifiability.** Every green check in this gate has to be shown capable of
   going red - the chokepoint scan against an injected `import httpx`, the
   invariant checkers against doctored reports. A check that cannot fail has not
   verified the thing that passed.

2. **One condition at a time.** The worker's hermetic handler has seven
   conditions. Exercising them only as a set would pass even if one were
   missing, so each is violated alone and must produce exactly its own reason.

3. **The distinctions this campaign exists to keep.** A hermetic proof is not a
   source having responded. A persisted payload is not a collection. A 404 is
   evidence and is not a finished job. Each of those is two fields, and each
   test reads both.
"""

from __future__ import annotations

import ast
import hashlib
import pathlib
import shutil
import uuid
from datetime import UTC, datetime, timedelta

import pytest
import sqlalchemy as sa
from fastapi.testclient import TestClient

from nativeforge.db.session import SessionLocal
from nativeforge.main import create_app
from nativeforge.repositories.source_collection_execution_attempt_repository import (
    ATTEMPTS,
    count_attempts,
    get_attempt,
    record_attempt,
)
from nativeforge.repositories.source_collection_job_repository import enqueue_job
from nativeforge.services import (
    source_collector_execution_artifact_gate161_service as art,
)
from nativeforge.services.hermetic_source_transport_service import (
    HermeticTransportRegistry,
    describe_hermetic_transport,
)
from nativeforge.services.source_collection_execution_chokepoint_service import (
    chokepoint_invariant_failures,
    scan_execution_chokepoint,
)
from nativeforge.services.source_collection_execution_policy_service import (
    build_execution_policy,
)
from nativeforge.services.source_collection_execution_proof_service import (
    HERMETIC_COMPLETION_SCOPE,
    LIVE_COMPLETION_SCOPE,
    PROOF_REQUIREMENTS,
    build_execution_proof,
    execution_proof_invariant_failures,
)
from nativeforge.services.source_collection_execution_retry_service import (
    MAX_RETRY_AFTER_SECONDS,
    evaluate_execution_retry,
    execution_retry_invariant_failures,
)
from nativeforge.services.source_collection_transport_service import (
    DISPATCHABLE_KINDS,
    HERMETIC,
    LIVE,
    describe_boundary,
    execute_request,
)
from nativeforge.services.source_collection_worker_runtime_service import (
    HANDLER_EVALUATE_ONLY,
    HANDLER_HERMETIC_EXECUTION,
    HERMETIC_REFUSALS,
    hermetic_execution_refusals,
    run_worker_cycle,
    worker_cycle_invariant_failures,
)
from nativeforge.services.source_collector_execution_health_service import (
    build_execution_health,
    execution_health_invariant_failures,
)
from nativeforge.services.source_collector_execution_service import (
    execute_collection,
    execution_invariant_failures,
)
from tests import session_org_helper as soh

DEMO = uuid.UUID("bbbbbbbb-cccc-dddd-eeee-ffffffffffff")
REAL = uuid.UUID("aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee")
T0 = datetime(2026, 9, 16, 12, 0, tzinfo=UTC)
REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]

BODY = b'{"opportunities":[{"number":"NF-161-T","title":"fixture"}]}'
#: Deliberately not valid UTF-8, with a null byte. A store that round-trips only
#: text passes every test written with a JSON fixture.
MALFORMED = b"\x00\xff\xfe not json, not xml, not anything \x80\x81"

URLS = {
    "ok": "https://fixtures.invalid/nf161/test/ok",
    "malformed": "https://fixtures.invalid/nf161/test/malformed",
    "timeout": "https://fixtures.invalid/nf161/test/timeout",
    "rate": "https://fixtures.invalid/nf161/test/429",
    "error": "https://fixtures.invalid/nf161/test/503",
    "notfound": "https://fixtures.invalid/nf161/test/404",
    "missing": "https://fixtures.invalid/nf161/test/unregistered",
}


def _registry() -> HermeticTransportRegistry:
    registry = HermeticTransportRegistry()
    registry.register_ok(URLS["ok"], BODY, etag='W/"nf161-test"')
    registry.register_malformed(URLS["malformed"])
    registry.register_timeout(URLS["timeout"], after_seconds=9.5)
    registry.register_rate_limited(URLS["rate"], retry_after=120)
    registry.register_server_error(URLS["error"], status_code=503)
    registry.register_not_found(URLS["notfound"])
    return registry


@pytest.fixture
def connection():
    soh.ensure_org(DEMO, "demo")
    session = SessionLocal()
    try:
        yield session
    finally:
        for table in (
            "nf_source_collection_execution_attempts",
            "nf_source_collection_raw_payloads",
            "nf_source_collection_job_leases",
            "nf_source_collection_jobs",
        ):
            try:
                session.execute(
                    sa.text(f"DELETE FROM {table} WHERE job_id LIKE :p"),
                    {"p": "nf161-test-%"},
                )
            except Exception:  # noqa: BLE001 - cleanup reports nothing
                session.rollback()
        session.commit()
        session.close()


def _run(connection, key, *, tag=None, **kw):
    stamp = tag or uuid.uuid4().hex[:8]
    source_id = kw.pop("source_id", f"nf161.fixture.test.{key}")
    job_id = f"nf161-test-{stamp}-{key}"
    enqueue_job(
        connection=connection,
        organization_id=DEMO,
        job_id=job_id,
        idempotency_key=job_id,
        source_id=source_id,
        schedule_key=f"nf161-test-{stamp}",
        scheduled_for=T0 - timedelta(minutes=5),
        now=T0,
    )
    return execute_collection(
        connection=connection,
        organization_id=kw.pop("organization_id", DEMO),
        job_id=job_id,
        source_definition={
            "source_id": source_id,
            "endpoint": URLS[key],
            "method": "GET",
        },
        transport=_registry().transport,
        now=T0,
        is_synthetic_fixture=kw.pop("is_synthetic_fixture", True),
        **kw,
    )


# ------------------------------------------------------------ the envelope


def test_the_exact_response_bytes_are_hashed_before_any_decoding(connection):
    """The hash is of what arrived, not of what a parser made of it."""
    report = _run(connection, "ok")
    assert report["bytes_received"] == len(BODY)
    assert report["raw_payload_sha256"] == hashlib.sha256(BODY).hexdigest()
    assert not execution_invariant_failures(report)


def test_a_malformed_body_is_persisted_and_is_not_a_failure(connection):
    """Parsing is a later gate's problem; the bytes are the only copy."""
    report = _run(connection, "malformed")
    assert report["response_received"] is True
    assert report["execution_status"] != "transport_failed"
    assert report["raw_payload_sha256"] == hashlib.sha256(MALFORMED).hexdigest()
    assert report["response_was_malformed"] is True


def test_an_attempt_row_is_written_for_every_outcome(connection):
    """A refusal and a timeout produce no payload, so the row is the record."""
    before = count_attempts(connection=connection, organization_id=DEMO)["total"]
    stamp = uuid.uuid4().hex[:8]
    for key in ("ok", "timeout", "notfound", "missing", "rate", "error"):
        _run(connection, key, tag=stamp)
    _run(
        connection,
        "ok",
        tag=f"{stamp}x",
        source_id="grants.gov",
        is_synthetic_fixture=False,
    )
    after = count_attempts(connection=connection, organization_id=DEMO)["total"]
    assert after - before == 7


def test_a_timeout_records_an_attempt_and_persists_nothing(connection):
    report = _run(connection, "timeout")
    assert report["execution_status"] == "transport_failed"
    assert report["refusal_reason"] == "transport_timeout"
    assert report["raw_payload_sha256"] is None
    assert report["attempt_recorded"] is True
    assert report["execution_proof_available"] is False


def test_an_unregistered_url_is_a_connection_failure_not_a_fetch(connection):
    report = _run(connection, "missing")
    assert report["refusal_reason"] == "transport_connection_failed"
    assert report["http_status"] is None
    assert report["network_calls"] == 0


def test_a_duplicate_attempt_is_refused_without_failing_an_invariant(connection):
    """Identity is deterministic, so the second pass is the same attempt."""
    stamp = uuid.uuid4().hex[:8]
    first = _run(connection, "ok", tag=stamp)
    second = _run(connection, "ok", tag=stamp)
    assert first["attempt_recorded"] is True
    assert second["attempt_recorded"] is False
    assert "this_attempt_has_already_been_recorded" in second["blocked_reasons"]
    # The row exists; the refusal to write it twice is not a missing record.
    assert not execution_invariant_failures(second)


# ----------------------------------------------------------- the refusals


def test_a_real_source_is_refused_by_the_hermetic_policy(connection):
    report = _run(connection, "ok", source_id="grants.gov", is_synthetic_fixture=False)
    assert report["execution_status"] == "refused_by_policy"
    assert report["refusal_reason"] == "not_a_synthetic_fixture"
    assert report["transport_invoked"] is False
    assert report["attempt_recorded"] is True


def test_the_real_organization_never_reaches_a_transport(connection):
    report = _run(connection, "ok", organization_id=REAL)
    assert report["transport_invoked"] is False
    assert report["attempt_recorded"] is False
    assert "real_organization_refused_by_name" in report["blocked_reasons"]


def test_live_is_refused_four_times_independently(connection):
    """Each stop is measured ALONE, with the ones before it satisfied.

    A chain of refusals tested only end to end could have three broken links
    and still refuse, which would make the depth imaginary.
    """
    # 1. the policy
    policy = build_execution_policy(
        source_id="nf161.fixture.test.ok",
        organization_id=DEMO,
        is_synthetic_fixture=True,
        transport_kind=LIVE,
    )
    assert policy["execution_allowed"] is False
    assert policy["live_transport_allowed"] is False

    # 2. the boundary, handed a policy that PERMITS - so what refuses here is
    #    the boundary and not the policy standing in front of it.
    from nativeforge.services.source_collection_request_builder_service import (
        build_source_request,
    )

    built = build_source_request(
        source_definition={
            "source_id": "nf161.fixture.test.ok",
            "endpoint": URLS["ok"],
            "method": "GET",
        }
    )
    permissive = dict(policy)
    permissive.update(
        execution_allowed=True,
        live_transport_allowed=True,
        hermetic_transport_allowed=True,
    )
    # Gate 163 made LIVE dispatchable, so the boundary no longer refuses the
    # kind outright. What it refuses now is a live dispatch that names no
    # authorized source - the same rule migration 0050 puts on the attempt
    # row. Still an INDEPENDENT stop: the policy above permits everything.
    #
    # Rewriting this to assert the policy refusal would collapse stop 2 into
    # stop 1 and make the depth this test exists to measure imaginary.
    dispatched = execute_request(
        request=built["transport_request"],
        transport_kind=LIVE,
        transport=_registry().transport,
        policy=permissive,
    )
    assert dispatched["dispatched"] is False
    assert (
        "a_live_dispatch_named_no_authorized_source" in (dispatched["blocked_reasons"])
    )

    # And the stop is falsifiable: naming an authorization reaches the
    # injected transport. A refusal no input can turn off is unfalsifiable,
    # which is the Gate 134F lesson in the permitting direction.
    authorized = dict(permissive, authorized_source_id="nf161.fixture.test.ok")
    reached = execute_request(
        request=built["transport_request"],
        transport_kind=LIVE,
        transport=_registry().transport,
        policy=authorized,
    )
    assert reached["dispatched"] is True
    assert "a_live_dispatch_named_no_authorized_source" not in (
        reached["blocked_reasons"] or []
    )

    # 3. and the warrant service refuses it
    #
    # Gate 163 put LIVE in DISPATCHABLE_KINDS, so "there is nothing to
    # dispatch to" stopped being true. The layer that became the third stop is
    # Gate 77B's canonical enforcement path, and it is independent of the two
    # above: no policy dict reaches it, and no boolean a caller supplies
    # changes its answer. It asks whether a recorded, signed authorization
    # names this source and this host.
    #
    # The permitted side needs the real recorded Gate 163 facts, which this
    # database does not have; `_g163_phase_warrant_negatives.py` asserts it,
    # which is what keeps this refusal falsifiable rather than unconditional.
    from nativeforge.services.source_live_warrant_service import (
        WARRANT_SOURCE_COLLECTION,
        evaluate_live_request,
    )

    warrant = evaluate_live_request(
        warrant_kind=WARRANT_SOURCE_COLLECTION,
        authorized_source_id="nf161.fixture.test.ok",
        request_url=URLS["ok"],
        method="GET",
        connection=connection,
        organization_id=DEMO,
    )
    assert warrant["permitted"] is False
    assert warrant["refusal_reasons"], "refused without saying why"

    # Dispatchable is not permitted, and the set says so plainly now.
    assert LIVE in DISPATCHABLE_KINDS
    assert HERMETIC in DISPATCHABLE_KINDS

    # 4. the database will not hold the row
    savepoint = connection.begin_nested()
    with pytest.raises(Exception):  # noqa: B017 - any refusal is the result
        connection.execute(
            sa.insert(ATTEMPTS).values(
                id=uuid.uuid4(),
                organization_id=DEMO,
                attempt_id="nf161-test-livekind",
                attempt_number=1,
                collector_version="v",
                job_id="nf161-test-livekind",
                source_id="s",
                started_at=T0,
                execution_status="response_received",
                transport_kind="live",
                refusal_reason="none",
                fact_status="synthetic_fixture",
            )
        )
    savepoint.rollback()


def test_the_database_refuses_a_row_claiming_a_live_call(connection):
    savepoint = connection.begin_nested()
    with pytest.raises(Exception):  # noqa: B017
        connection.execute(
            sa.insert(ATTEMPTS).values(
                id=uuid.uuid4(),
                organization_id=DEMO,
                attempt_id="nf161-test-livecall",
                attempt_number=1,
                collector_version="v",
                job_id="nf161-test-livecall",
                source_id="s",
                started_at=T0,
                execution_status="response_received",
                transport_kind="hermetic",
                refusal_reason="none",
                fact_status="synthetic_fixture",
                live_source_call=True,
            )
        )
    savepoint.rollback()


def test_a_proof_needs_a_persisted_payload_and_the_database_says_so(connection):
    """The CHECK, not the service. A service can be bypassed; a CHECK cannot."""
    savepoint = connection.begin_nested()
    with pytest.raises(Exception):  # noqa: B017
        connection.execute(
            sa.insert(ATTEMPTS).values(
                id=uuid.uuid4(),
                organization_id=DEMO,
                attempt_id="nf161-test-proofless",
                attempt_number=1,
                collector_version="v",
                job_id="nf161-test-proofless",
                source_id="s",
                started_at=T0,
                execution_status="response_received",
                transport_kind="hermetic",
                refusal_reason="none",
                fact_status="synthetic_fixture",
                execution_proof_available=True,
                raw_payload_persisted=False,
            )
        )
    savepoint.rollback()


# --------------------------------------------------------------- the proof


def test_the_proof_reports_what_it_proves_and_what_it_does_not(connection):
    report = _run(connection, "ok")
    proof = report["proof"]
    assert proof["proves_the_envelope_works"] is True
    # The field that must never become the one above.
    assert proof["proves_a_source_responded"] is False
    assert proof["permits_real_source_job_completion"] is False
    assert proof["proof_scope"] == HERMETIC_COMPLETION_SCOPE
    assert not execution_proof_invariant_failures(proof)


def test_a_404_is_evidenced_and_completes_nothing(connection):
    """Two facts: the envelope worked, and there was nothing there."""
    report = _run(connection, "notfound")
    proof = report["proof"]
    assert proof["execution_proof_available"] is True
    assert proof["response_was_usable"] is False
    assert proof["permits_hermetic_job_completion"] is False
    assert not execution_proof_invariant_failures(proof)


def test_the_proof_checker_catches_a_proof_that_claims_too_much():
    """Each lie separately, because a checker is only as good as its worst case."""
    base = build_execution_proof(
        attempt={"attempt_id": "a", "transport_kind": HERMETIC},
        payload={},
        replay={},
        policy={},
        transport_result={},
    )
    assert "the_proof_claimed_a_source_responded" in (
        execution_proof_invariant_failures(dict(base, proves_a_source_responded=True))
    )
    assert "the_proof_permitted_a_real_source_job_to_complete" in (
        execution_proof_invariant_failures(
            dict(base, permits_real_source_job_completion=True)
        )
    )
    assert "a_live_scoped_proof_was_produced" in (
        execution_proof_invariant_failures(
            dict(base, proof_scope=LIVE_COMPLETION_SCOPE)
        )
    )
    assert "proof_available_alongside_unmet_requirements" in (
        execution_proof_invariant_failures(dict(base, execution_proof_available=True))
    )


def test_every_proof_requirement_is_named_and_evidenced(connection):
    report = _run(connection, "ok")
    proof = report["proof"]
    assert len(PROOF_REQUIREMENTS) == 7
    assert set(proof["requirements"]) == set(PROOF_REQUIREMENTS)
    for name in PROOF_REQUIREMENTS:
        assert proof["requirement_evidence"][name].strip(), name


# --------------------------------------------------------------- the retry


def test_retry_classification_matches_the_outcome():
    cases = {
        ("timeout", None): ("transient_worker_failure", True),
        ("connection_failed", None): ("transient_worker_failure", True),
        ("response_received", 429): ("transient_worker_failure", True),
        ("response_received", 503): ("transient_worker_failure", True),
        ("response_received", 404): ("permanent_worker_failure", False),
        ("response_received", 401): ("permanent_worker_failure", False),
        ("response_received", 200): ("none", False),
        ("response_received_malformed_body", 200): ("none", False),
        ("refused_before_dispatch", None): ("none", False),
    }
    for (outcome, status), (klass, retried) in cases.items():
        decision = evaluate_execution_retry(outcome=outcome, http_status=status, now=T0)
        assert decision["failure_class"] == klass, (outcome, status)
        assert decision["should_retry"] is retried, (outcome, status)
        assert not execution_retry_invariant_failures(decision)


def test_a_sources_retry_after_wins_over_the_computed_backoff():
    decision = evaluate_execution_retry(
        outcome="response_received",
        http_status=429,
        response_headers={"Retry-After": "120"},
        now=T0,
    )
    assert decision["retry_after_was_honoured"] is True
    assert decision["backoff_seconds"] == 120
    # It genuinely OVERRODE something, rather than coinciding with it.
    assert decision["computed_backoff_seconds"] != 120
    assert decision["schedule_source"] == "the_sources_retry_after"


def test_an_absurd_retry_after_is_capped_and_says_so():
    decision = evaluate_execution_retry(
        outcome="response_received",
        http_status=429,
        response_headers={"Retry-After": "999999"},
        now=T0,
    )
    assert decision["backoff_seconds"] == MAX_RETRY_AFTER_SECONDS
    assert decision["retry_after_notes"], "the cap was applied silently"


def test_an_unparseable_retry_after_falls_back_and_says_so():
    decision = evaluate_execution_retry(
        outcome="response_received",
        http_status=429,
        response_headers={"Retry-After": "Wed, 21 Oct 2026 07:28:00 GMT"},
        now=T0,
    )
    assert decision["retry_after_was_honoured"] is False
    assert decision["backoff_seconds"] == decision["computed_backoff_seconds"]
    assert decision["retry_after_notes"]


def test_a_human_blocker_is_never_retried():
    for reason in (
        "refused_by_activation",
        "terms_blocked",
        "human_review_blocked",
    ):
        decision = evaluate_execution_retry(
            outcome="timeout", refusal_reasons=[reason], now=T0
        )
        assert decision["should_retry"] is False, reason
        assert decision["classification"]["decided_by"] == "a_human_blocker"


def test_the_retry_checker_catches_a_retried_permanent_failure():
    honest = evaluate_execution_retry(
        outcome="response_received", http_status=404, now=T0
    )
    liar = dict(honest, should_retry=True, next_retry_at="2026-09-16T12:01:00")
    assert "retried_a_non_transient_class:permanent_worker_failure" in (
        execution_retry_invariant_failures(liar)
    )


# -------------------------------------------------------------- the worker


def test_each_hermetic_refusal_condition_fires_alone():
    """Seven conditions. A set exercised only as a set could be missing one."""

    def job(**overrides):
        base = {
            "job_id": "nf161-test-j",
            "source_id": "nf161.fixture.test.worker",
            "executable": True,
            "blockers": [],
            "hermetic_fixture": True,
            "source_definition": {"source_id": "nf161.fixture.test.worker"},
        }
        base.update(overrides)
        return base

    transport = _registry().transport
    seen = {}

    seen["handler_is_not_hermetic_execution"] = hermetic_execution_refusals(
        job(), handler=HANDLER_EVALUATE_ONLY, transport=transport
    )
    seen["no_hermetic_transport_was_injected"] = hermetic_execution_refusals(
        job(), handler=HANDLER_HERMETIC_EXECUTION, transport=None
    )
    seen["job_is_not_declared_a_hermetic_fixture"] = hermetic_execution_refusals(
        job(hermetic_fixture=False),
        handler=HANDLER_HERMETIC_EXECUTION,
        transport=transport,
    )
    seen["executable_is_not_a_persisted_fact_in_gate_158"] = (
        hermetic_execution_refusals(
            job(loaded_from_store=True),
            handler=HANDLER_HERMETIC_EXECUTION,
            transport=transport,
        )
    )
    seen["the_scheduler_did_not_mark_this_job_executable"] = (
        hermetic_execution_refusals(
            job(executable=False),
            handler=HANDLER_HERMETIC_EXECUTION,
            transport=transport,
        )
    )
    seen["job_carries_no_source_definition"] = hermetic_execution_refusals(
        job(source_definition=None),
        handler=HANDLER_HERMETIC_EXECUTION,
        transport=transport,
    )
    seen["source_id_is_not_a_synthetic_fixture"] = hermetic_execution_refusals(
        job(source_id="grants.gov", source_definition={"source_id": "grants.gov"}),
        handler=HANDLER_HERMETIC_EXECUTION,
        transport=transport,
    )

    assert set(seen) == set(HERMETIC_REFUSALS)
    for expected, produced in seen.items():
        assert produced == [expected], (expected, produced)

    # And all seven satisfied produces none.
    assert (
        hermetic_execution_refusals(
            job(), handler=HANDLER_HERMETIC_EXECUTION, transport=transport
        )
        == []
    )


def test_a_fixture_prefix_alone_is_not_enough():
    """`nf161.fixture.` with nothing after it is not a source."""
    refusals = hermetic_execution_refusals(
        {
            "source_id": "nf161.fixture.",
            "executable": True,
            "hermetic_fixture": True,
            "source_definition": {"source_id": "nf161.fixture."},
        },
        handler=HANDLER_HERMETIC_EXECUTION,
        transport=_registry().transport,
    )
    assert refusals == ["source_id_is_not_a_synthetic_fixture"]


def _worker_job(stamp, tag, source_id="nf161.fixture.test.worker"):
    return {
        "job_id": f"nf161-test-{stamp}-{tag}",
        "source_id": source_id,
        "executable": True,
        "blockers": [],
        "hermetic_fixture": True,
        "source_definition": {
            "source_id": source_id,
            "endpoint": URLS["ok"],
            "method": "GET",
        },
    }


def _worker_cycle(connection, jobs, **kw):
    for job in jobs:
        enqueue_job(
            connection=connection,
            organization_id=DEMO,
            job_id=job["job_id"],
            idempotency_key=job["job_id"],
            source_id=job["source_id"],
            schedule_key="nf161-test",
            scheduled_for=T0 - timedelta(minutes=5),
            now=T0,
        )
    return run_worker_cycle(
        connection=connection,
        organization_id=DEMO,
        worker_id="nf161-test-worker",
        jobs=jobs,
        now=T0,
        **kw,
    )


def test_a_hermetic_job_flows_through_the_worker_and_completes_nothing(
    connection,
):
    stamp = uuid.uuid4().hex[:8]
    cycle = _worker_cycle(
        connection,
        [_worker_job(stamp, "run")],
        handler=HANDLER_HERMETIC_EXECUTION,
        transport=_registry().transport,
    )
    assert cycle["hermetic_executions"] == 1
    assert cycle["hermetic_payloads_persisted"] == 1
    assert cycle["hermetic_execution_proofs"] == 1
    assert cycle["raw_payloads_written"] == 1
    # The job asked for a source to be collected. A fixture answered.
    assert cycle["jobs_completed"] == 0
    assert cycle["hermetic_execution_means_collection_occurred"] is False
    assert not worker_cycle_invariant_failures(cycle)


def test_the_default_worker_handler_is_unchanged(connection):
    stamp = uuid.uuid4().hex[:8]
    cycle = _worker_cycle(connection, [_worker_job(stamp, "default")])
    assert cycle["hermetic_executions"] == 0
    assert cycle["raw_payloads_written"] == 0
    assert cycle["jobs_completed"] == 0
    assert not worker_cycle_invariant_failures(cycle)


def test_the_worker_refuses_a_real_source_with_the_handler_and_a_transport(
    connection,
):
    """Handler asked for, transport in hand, and it still refuses."""
    stamp = uuid.uuid4().hex[:8]
    cycle = _worker_cycle(
        connection,
        [_worker_job(stamp, "real", source_id="grants.gov")],
        handler=HANDLER_HERMETIC_EXECUTION,
        transport=_registry().transport,
    )
    assert cycle["hermetic_executions"] == 0
    assert cycle["raw_payloads_written"] == 0
    reasons = cycle["results"][0]["blocked_reasons"]
    assert "source_id_is_not_a_synthetic_fixture" in reasons


def test_the_live_counters_stay_zero_under_the_hermetic_handler(connection):
    stamp = uuid.uuid4().hex[:8]
    cycle = _worker_cycle(
        connection,
        [_worker_job(stamp, "counters")],
        handler=HANDLER_HERMETIC_EXECUTION,
        transport=_registry().transport,
    )
    for counter in (
        "collectors_invoked",
        "live_source_calls",
        "network_calls",
        "urls_fetched",
        "threads_started",
    ):
        assert cycle[counter] == 0, counter
    assert cycle["source_monitoring_live"] is False


def test_the_worker_checker_catches_a_payload_count_that_disagrees(connection):
    stamp = uuid.uuid4().hex[:8]
    cycle = _worker_cycle(
        connection,
        [_worker_job(stamp, "liar")],
        handler=HANDLER_HERMETIC_EXECUTION,
        transport=_registry().transport,
    )
    liar = dict(cycle, raw_payloads_written=9)
    assert "raw_payloads_written_disagrees_with_the_hermetic_count" in (
        worker_cycle_invariant_failures(liar)
    )
    liar2 = dict(cycle, handler=HANDLER_EVALUATE_ONLY)
    assert f"a_hermetic_execution_under_handler:{HANDLER_EVALUATE_ONLY}" in (
        worker_cycle_invariant_failures(liar2)
    )


# ---------------------------------------------------------- the chokepoint


def test_no_envelope_module_imports_a_network_module():
    scan = scan_execution_chokepoint(repo_root=REPO_ROOT)
    assert scan["modules_that_reach_a_host"] == []
    assert scan["envelope_reaches_no_host"] is True
    assert scan["findings"] == []
    assert not chokepoint_invariant_failures(scan)


def test_the_chokepoint_scan_fails_on_an_injected_import(tmp_path):
    """The green is only worth something if red is reachable."""
    shutil.copytree(REPO_ROOT / "src", tmp_path / "src")
    victim = (
        tmp_path
        / "src/nativeforge/services/source_collection_execution_proof_service.py"
    )
    victim.write_text("import httpx\n" + victim.read_text(), encoding="utf-8")

    scan = scan_execution_chokepoint(repo_root=tmp_path)
    kinds = {f["kind"] for f in scan["findings"]}
    assert "envelope_module_imports_a_network_module" in kinds
    assert scan["envelope_reaches_no_host"] is False
    assert chokepoint_invariant_failures(scan)


def test_the_chokepoint_scan_fails_on_a_renamed_module(tmp_path):
    """A scan that silently skips what it cannot find reports nothing at all."""
    shutil.copytree(REPO_ROOT / "src", tmp_path / "src")
    (
        tmp_path
        / "src/nativeforge/services/source_collection_execution_retry_service.py"
    ).unlink()

    scan = scan_execution_chokepoint(repo_root=tmp_path)
    kinds = {f["kind"] for f in scan["findings"]}
    assert "envelope_module_missing" in kinds
    assert scan["modules_found"] < len(scan["modules_expected"])


def test_the_chokepoint_uses_ast_and_not_a_substring_search():
    """Measured by parsing. Asserting it in prose would be the defect itself."""
    source = (
        REPO_ROOT
        / "src/nativeforge/services"
        / "source_collection_execution_chokepoint_service.py"
    )
    tree = ast.parse(source.read_text(encoding="utf-8"))
    uses_ast = {
        node.value.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name)
    }
    assert "ast" in uses_ast

    # And `re` is not imported at all, so no regex scan can be hiding in it.
    imported = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    assert "re" not in imported


def test_both_transport_modules_prove_they_reach_no_host():
    """Each parses ITSELF, so the claim is derived rather than written down."""
    assert describe_boundary()["reaches_a_host"] is False
    assert describe_hermetic_transport()["reaches_a_host"] is False
    assert describe_boundary()["live_transport_implemented_here"] is False


# -------------------------------------------------------------- the health


def test_the_health_lane_separates_knowing_from_approving(connection):
    health = build_execution_health(connection=connection, organization_id=DEMO)
    assert health["approved_source_count"] == 0
    assert health["monitorable_source_count"] == 0
    # The registry is FULL. A zero that came from an empty registry would be
    # the same number for an entirely different reason.
    assert health["known_source_count"] > 0
    assert health["known_is_not_approved"].strip()
    assert not execution_health_invariant_failures(health)


def test_the_health_lane_reports_a_live_transport_that_needs_permission(
    connection,
):
    """Available is not enabled, and neither is proven.

    Gate 161 asserted `live_transport_available is False` because no
    implementation existed. Gate 163 built one, so the lane reports True and
    what is left to assert is every distinction that survived it.
    """
    health = build_execution_health(connection=connection, organization_id=DEMO)

    # An implementation exists. That is the true state, and refusing it would
    # only teach the next reader to edit the invariant.
    assert health["live_transport_available"] is True
    assert "live" in health["dispatchable_kinds"]

    # None of which is permission, a proof, or a running monitor.
    assert health["live_transport_enabled"] is False
    assert health["live_execution_proven"] is False
    assert health["source_monitoring_live"] is False

    # And it cannot dispatch without an authorization - measured by the lane
    # attempting one, not declared.
    assert health["conditions"]["live_transport_requires_an_authorization"] is True
    assert health["not_implied"], "the lane did not say what it does not imply"


def test_the_health_checker_catches_a_lane_that_claims_live(connection):
    health = build_execution_health(connection=connection, organization_id=DEMO)
    # `live_transport_available=True` is no longer a lie to inject - an
    # implementation exists. The lie is a lane claiming live needs no
    # authorization, so that is what goes in.
    assert "live_can_dispatch_without_an_authorization" in (
        execution_health_invariant_failures(
            dict(
                health,
                conditions=dict(
                    health["conditions"],
                    live_transport_requires_an_authorization=False,
                ),
            )
        )
    )
    # Enabled is still a claim nothing may make.
    assert "health_claimed:live_transport_enabled" in (
        execution_health_invariant_failures(dict(health, live_transport_enabled=True))
    )
    assert "health_counted:approved_source_count=3" in (
        execution_health_invariant_failures(dict(health, approved_source_count=3))
    )


# -------------------------------------------------------------- the routes


def test_no_route_takes_a_url_parameter():
    """Structural, not defensive. A route told no address cannot be pointed."""
    client = TestClient(create_app())
    spec = client.get("/openapi.json").json()
    address_words = {
        "url",
        "uri",
        "endpoint",
        "host",
        "address",
        "target",
        "fetch",
        "callback",
        "redirect",
        "proxy",
        "location",
    }
    paths = {
        path: ops
        for path, ops in spec["paths"].items()
        if "collector-execution" in path
    }
    assert len(paths) >= 3
    for path, ops in paths.items():
        for method, operation in ops.items():
            for parameter in operation.get("parameters") or []:
                words = set(str(parameter["name"]).replace("-", "_").lower().split("_"))
                assert not (words & address_words), (method, path, parameter)


def test_the_smoke_route_takes_no_request_body():
    client = TestClient(create_app())
    spec = client.get("/openapi.json").json()
    smoke = [
        ops
        for path, ops in spec["paths"].items()
        if path.endswith("/collector-execution/smoke")
    ]
    assert smoke
    assert not smoke[0]["post"].get("requestBody")


def test_the_smoke_route_writes_and_rolls_back(connection):
    soh.ensure_org(DEMO, "demo")
    client = TestClient(create_app())
    response = client.post(
        f"/v1/nf/demo/orgs/{DEMO}/collector-execution/smoke",
        headers=soh.session_headers(DEMO),
    )
    assert response.status_code == 200
    body = response.json().get("data", response.json())

    # The rollback only means something if there was something to roll back.
    assert body["attempt_rows_during"] > body["attempt_rows_before"]
    assert body["attempt_rows_after"] == body["attempt_rows_before"]
    assert body["rolled_back"] is True
    assert body["smoke"]["execution_proof_available"] is True
    assert body["proves_a_source_responded"] is False
    assert body["caller_can_supply_a_url"] is False
    assert not body["invariant_failures"]


def test_the_routes_refuse_a_request_without_a_session():
    client = TestClient(create_app())
    for method, suffix in (
        ("get", "health"),
        ("get", "attempts"),
        ("post", "smoke"),
    ):
        response = getattr(client, method)(
            f"/v1/nf/demo/orgs/{DEMO}/collector-execution/{suffix}"
        )
        assert response.status_code >= 400, (method, suffix)


def test_the_real_organization_is_refused_by_the_routes():
    soh.ensure_org(DEMO, "demo")
    client = TestClient(create_app())
    response = client.get(
        f"/v1/nf/demo/orgs/{REAL}/collector-execution/health",
        headers=soh.session_headers(DEMO),
    )
    assert response.status_code == 404


# ------------------------------------------------------------ the artifacts


def test_the_artifacts_on_disk_match_what_the_builder_produces():
    directory = REPO_ROOT / art.ARTIFACT_DIR
    for name, body in art.build_execution_artifacts().items():
        assert (directory / name).read_text(encoding="utf-8") == body, name


def test_the_artifacts_are_deterministic_across_processes():
    """In a SEPARATE process, with a different hash seed.

    Calling the builder twice in one process compares set iteration order
    against itself, which is stable there - so it passed while the artifacts
    contained unsorted frozensets and every real rebuild produced different
    bytes. PYTHONHASHSEED is the thing that actually varies, so that is what
    this varies.
    """
    import json
    import os
    import subprocess
    import sys

    script = (
        "import json;"
        "from nativeforge.services import "
        "source_collector_execution_artifact_gate161_service as art;"
        "print(json.dumps(art.build_execution_artifacts()))"
    )
    bodies = []
    for seed in ("1", "424242"):
        environment = dict(os.environ, PYTHONHASHSEED=seed)
        environment["PYTHONPATH"] = str(REPO_ROOT / "src")
        result = subprocess.run(
            [sys.executable, "-c", script],
            capture_output=True,
            text=True,
            cwd=REPO_ROOT,
            env=environment,
            check=True,
        )
        bodies.append(json.loads(result.stdout))

    assert bodies[0] == bodies[1]
    # And the process output matches this process, so the files on disk are
    # what any rebuild would produce.
    assert bodies[0] == art.build_execution_artifacts()


def test_every_declared_artifact_file_exists():
    directory = REPO_ROOT / art.ARTIFACT_DIR
    for name in art.ARTIFACT_FILES:
        assert (directory / name).exists(), name
    assert len(art.ARTIFACT_FILES) == 12


def test_the_artifacts_say_source_monitoring_is_not_live():
    files = art.build_execution_artifacts()
    status = files["source_monitoring_status.json"]
    assert '"source_monitoring_live": false' in status
    assert '"approved_source_count": 0' in status
    assert '"live_transport_implemented": false' in status


# ------------------------------------------------------------ the attempt row


def test_the_stored_row_agrees_with_the_report(connection):
    report = _run(connection, "ok")
    found = get_attempt(
        connection=connection,
        organization_id=DEMO,
        attempt_id=report["execution_attempt_id"],
    )
    row = found["attempt"]
    assert row is not None
    assert row["raw_payload_sha256"] == report["raw_payload_sha256"]
    assert row["bytes_received"] == report["bytes_received"]
    assert row["transport_kind"] == HERMETIC
    assert row["live_source_call"] is False
    assert row["execution_proof_available"] is True


def test_the_repository_refuses_an_attempt_for_the_real_organization(connection):
    written = record_attempt(
        connection=connection,
        organization_id=REAL,
        attempt_id="nf161-test-realorg",
        job_id="nf161-test-realorg",
        source_id="s",
        started_at=T0,
    )
    assert written["recorded"] is False
    assert "real_organization_refused_by_name" in written["blocked_reasons"]
