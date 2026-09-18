"""Exercise the source runtime lanes right now (Gate 163U).

`runtime_status` answers "can the required runtime actually operate", and the
four lane health builders answer it from evidence somebody else produced. Three
of them take no connection at all: `build_raw_payload_health` "reports the lane
from results somebody else measured, so it cannot pass its own lane by doing
the work it is grading." Called cold they report `table_exists` unmet while the
table holds rows - correct, and not readiness.

The exercise orchestration lived in three verifier phase scripts, which is fine
for a verifier and useless to a dispatch path. This is the minimum extracted so
the collection path can measure the lanes immediately before authorization.

The question it answers is "can this operate NOW", not "did a verifier once
prove it". See doc 848 for the survey of what each script exercised and which
parts were ceremony.

## It commits, so it cleans up

`collection_job_store_ready` requires `survives_restart`: a row written by one
connection, read back by another. An uncommitted row is invisible to a second
connection by definition, so a savepoint cannot produce that evidence - using
one would quietly turn the condition into something nothing measures.

So every probe write is committed on its own engine connection, and cleanup runs
after the last probe write of each lane, deletes by this run's own fixture ids,
and COUNTS what it removed. Never by organization: the Gate 157 verifier opens
with `DELETE ... WHERE organization_id = :o`, which is correct for a verifier
that owns the demo org for its run and wrong for a dispatch path that would be
deleting rows it did not create.

## Lane 4 is free

`collector_execution_envelope_ready` reads the attempt table itself and writes
nothing. It is the one lane whose health builder does its own measuring, so it
is observed rather than exercised.

## What it will not do

No network, no email, no object store. No source activation, opt-in or decision
write - readiness is not permission, and a module that could touch both would
be one edit away from conflating them. The lane-2 fixture job is this
exerciser's own and is deleted; that is a different thing from the collection
inventing a durable scheduler job to satisfy readiness, which it must not do.
"""

from __future__ import annotations

import datetime as dt
import json
import uuid
from typing import Any

SCHEMA_VERSION = "nf_source_runtime_lane_exerciser_v1"

CONTROLLED_SCOPE = "controlled_dev_demo"

#: Reserved. Every row this module writes carries one of these ids, and cleanup
#: deletes by them and nothing else.
FIXTURE_PREFIX = "nf163.exercise."

WORKER_LANE = "worker_runtime_ready"
JOB_STORE_LANE = "collection_job_store_ready"
PAYLOAD_LANE = "raw_payload_persistence_ready"
ENVELOPE_LANE = "collector_execution_envelope_ready"

#: The lanes a source collection requires, in the order a reader wants them.
REQUIRED_LANES: tuple[str, ...] = (
    ENVELOPE_LANE,
    WORKER_LANE,
    JOB_STORE_LANE,
    PAYLOAD_LANE,
)

READY = "ready"
NOT_READY = "not_ready"

#: Headers the payload lane needs in order to have something to refuse and
#: something to keep. Not decoration: `secret_headers_refused` and
#: `safe_headers_survive` are both conditions.
PROBE_HEADERS: dict[str, str] = {
    "Content-Type": "application/json",
    "ETag": 'W/"nf163-exercise"',
    "Authorization": "Bearer must-be-refused",
    "Cookie": "must=be-refused",
    "Set-Cookie": "must=be-refused",
    "X-API-Key": "must-be-refused",
    "X-Nf163-Unrecognised": "must-be-refused",
}

PROBE_BODY = b'{"synthetic":true,"lane":"nf163.exercise"}'

NOT_IMPLIED: tuple[str, ...] = (
    "readiness is not authorization - no decision record is read here",
    "readiness is not an opt-in - nothing here permits a request",
    "a ready runtime still refuses a live request without a warrant",
    "this measures NOW; it is not a stored claim and is never persisted",
)


def _json_safe(value: Any) -> Any:
    return json.loads(json.dumps(value, default=str, sort_keys=True))


def _table_exists(engine: Any, table: str) -> bool:
    """Measured against the schema.

    Both surveyed phase scripts pass `table_exists=True` as a literal. It is
    true, and it is not measured - so a missing table would surface as some
    later condition failing for an unexplained reason.
    """
    try:
        import sqlalchemy as sa

        return sa.inspect(engine).has_table(table)
    except Exception:  # noqa: BLE001 - an unreadable schema is not a present one
        return False


def _conditions_of(health: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    """Normalise the two shapes the lane health builders return.

    `build_worker_health` returns `conditions` as a LIST of condition names and
    puts the measurements in `conditions_met` / `conditions_missing`. The other
    two return `conditions` as a dict of name -> bool. Reading `.items()` on
    the first shape raises, which is how a lane that had measured everything
    correctly came to report `lane_raised:AttributeError`.
    """
    conditions = health.get("conditions")
    if isinstance(conditions, dict):
        return conditions, sorted(k for k, v in conditions.items() if v is not True)

    measured = health.get("conditions_met")
    if isinstance(measured, dict):
        missing = health.get("conditions_missing") or health.get("conditions_not_met")
        if not isinstance(missing, list):
            missing = sorted(k for k, v in measured.items() if v is not True)
        return measured, sorted(str(name) for name in missing)

    # Neither shape. Say so rather than reporting an empty condition set, which
    # would read as "nothing failed".
    return {}, ["conditions_were_not_reported_in_a_readable_shape"]


def _lane(
    name: str,
    *,
    exercised: bool,
    ready: bool,
    conditions: dict[str, Any] | None = None,
    unmet: list[str] | None = None,
    evidence: dict[str, Any] | None = None,
    cleanup_count: int = 0,
) -> dict[str, Any]:
    return {
        "lane_name": name,
        "exercised": bool(exercised),
        "ready": bool(ready),
        "conditions": conditions or {},
        "unmet_conditions": sorted(unmet or []),
        "evidence": evidence or {},
        "cleanup_count": int(cleanup_count),
    }


# ------------------------------------------------------------ lane 4
def _observe_envelope(*, connection: Any, organization_id: Any) -> dict[str, Any]:
    """Observed, not exercised. This lane measures itself and writes nothing."""
    try:
        from nativeforge.services.source_collector_execution_health_service import (
            build_execution_health,
            execution_health_invariant_failures,
        )

        health = build_execution_health(
            connection=connection, organization_id=organization_id
        )
    except Exception as exc:  # noqa: BLE001
        return _lane(
            ENVELOPE_LANE,
            exercised=False,
            ready=False,
            unmet=[f"lane_could_not_be_observed:{type(exc).__name__}"],
        )

    conditions, unmet = _conditions_of(health)
    failures = execution_health_invariant_failures(health)
    return _lane(
        ENVELOPE_LANE,
        exercised=True,
        ready=bool(health.get("execution_envelope_ready")) and not failures,
        conditions=conditions,
        unmet=unmet + [f"invariant:{f}" for f in failures],
        evidence={
            "measures_itself": True,
            "writes_nothing": True,
            "attempts_recorded": health.get("attempts_recorded"),
            "conditions_not_met": health.get("conditions_not_met"),
        },
    )


# ------------------------------------------------------------ lane 1
def _exercise_worker(
    *, engine: Any, organization_id: Any, stamp: str, now: dt.datetime
) -> dict[str, Any]:
    """A real claim, a refused duplicate, and a reclaim after the lease expires."""
    import sqlalchemy as sa

    from nativeforge.services.source_collection_job_lease_service import (
        DEFAULT_LEASE_SECONDS,
        TABLE_NAME,
        claim_job,
    )
    from nativeforge.services.source_collection_retry_policy_service import (
        TRANSIENT_WORKER_FAILURE,
        evaluate_retry,
    )
    from nativeforge.services.source_collection_worker_health_service import (
        build_worker_health,
        worker_health_invariant_failures,
    )
    from nativeforge.services.source_collection_worker_runtime_service import (
        run_worker_cycle,
        worker_cycle_invariant_failures,
    )

    source_id = f"{FIXTURE_PREFIX}{stamp}.worker"
    job_id = f"{FIXTURE_PREFIX}{stamp}.worker.job"
    # Past the default lease, so the reclaim is a reclaim and not a second
    # claim inside a live lease.
    later = now + dt.timedelta(seconds=DEFAULT_LEASE_SECONDS + 60)

    evidence: dict[str, Any] = {}
    cleaned = 0
    try:
        with engine.begin() as connection:
            first = claim_job(
                connection=connection,
                organization_id=organization_id,
                job_id=job_id,
                source_id=source_id,
                worker_id=f"{FIXTURE_PREFIX}{stamp}.worker.a",
                now=now,
            )
        with engine.begin() as connection:
            duplicate = claim_job(
                connection=connection,
                organization_id=organization_id,
                job_id=job_id,
                source_id=source_id,
                worker_id=f"{FIXTURE_PREFIX}{stamp}.worker.b",
                now=now,
            )
        with engine.begin() as connection:
            reclaim = claim_job(
                connection=connection,
                organization_id=organization_id,
                job_id=job_id,
                source_id=source_id,
                worker_id=f"{FIXTURE_PREFIX}{stamp}.worker.b",
                now=later,
            )

        # Pure. No database, and the bound is the point: an exhausted attempt
        # count must not retry.
        exhausted = evaluate_retry(
            failure_class=TRANSIENT_WORKER_FAILURE,
            attempt_count=3,
            max_attempts=3,
            now=now,
        )

        with engine.begin() as connection:
            cycle = run_worker_cycle(
                connection=connection,
                organization_id=organization_id,
                worker_id=f"{FIXTURE_PREFIX}{stamp}.worker.cycle",
                jobs=[
                    {
                        "job_id": f"{FIXTURE_PREFIX}{stamp}.worker.cycle.job",
                        "source_id": source_id,
                        # Not executable, and that is deliberate: a cycle that
                        # COMPLETED a job would be a collection nothing
                        # authorized. The lane asks whether the worker can run
                        # a pass, not whether it can collect.
                        "executable": False,
                        "blockers": ["source_terms_not_approved"],
                    }
                ],
                now=now,
                record_job_transitions=False,
            )

        evidence = {
            "first_claim_succeeded": bool(first.get("claimed")),
            "duplicate_refused_reasons": duplicate.get("blocked_reasons"),
            "reclaimed_after_expiry": bool(reclaim.get("claimed")),
            "retry_bounded_at": 3,
            "cycle_jobs_seen": cycle.get("jobs_seen"),
            "cycle_jobs_completed": cycle.get("jobs_completed"),
            "lease_seconds": DEFAULT_LEASE_SECONDS,
        }

        health = build_worker_health(
            cycle=cycle,
            duplicate_claim_refused=not duplicate.get("claimed"),
            expired_lease_reclaimed=bool(reclaim.get("claimed")),
            retry_bounded=not exhausted.get("should_retry"),
            worker_process_active=None,
            jobs_available=1,
            jobs_claimable=0,
            stale_leases=0,
            activation_allowlist_count=0,
        )
        failures = worker_health_invariant_failures(
            health
        ) + worker_cycle_invariant_failures(cycle)
        conditions, unmet = _conditions_of(health)
        ready = bool(health.get("worker_runtime_ready")) and not failures
        exercised = True
    except Exception as exc:  # noqa: BLE001 - an unexercisable lane is not ready
        # Recorded, NOT returned. Returning here built the result before
        # `finally` computed `cleaned`, so a failing lane reported
        # cleanup_count 0 while cleanup had run - a number that read the same
        # whether or not anything was cleaned.
        raised = f"lane_raised:{type(exc).__name__}:{exc}"
        conditions, unmet, ready, failures = {}, [raised], False, []
        exercised = False
    finally:
        # AFTER the last probe write of this lane, by this run's ids only.
        try:
            with engine.begin() as connection:
                cleaned = int(
                    connection.execute(
                        sa.text(
                            f"DELETE FROM {TABLE_NAME} "  # noqa: S608 - a constant
                            "WHERE job_id LIKE :pattern"
                        ),
                        {"pattern": f"{FIXTURE_PREFIX}{stamp}.worker%"},
                    ).rowcount
                    or 0
                )
        except Exception:  # noqa: BLE001
            cleaned = -1

    return _lane(
        WORKER_LANE,
        exercised=exercised,
        ready=ready,
        conditions=conditions,
        unmet=list(unmet) + [f"invariant:{f}" for f in failures],
        evidence=evidence,
        cleanup_count=cleaned,
    )


# ------------------------------------------------------------ lane 2
def _exercise_job_store(
    *, engine: Any, organization_id: Any, stamp: str, now: dt.datetime
) -> dict[str, Any]:
    """An idempotent enqueue, a re-read on a NEW connection, an illegal move."""
    import sqlalchemy as sa

    from nativeforge.repositories.source_collection_job_repository import (
        REFUSED,
        count_backlog,
        enqueue_job,
        list_jobs,
        transition_job,
    )
    from nativeforge.services.source_collection_job_identity_service import (
        build_job_identity,
    )
    from nativeforge.services.source_collection_job_store_health_service import (
        build_job_store_health,
        job_store_health_invariant_failures,
    )

    source_id = f"{FIXTURE_PREFIX}{stamp}.jobstore"
    identity = build_job_identity(source_id=source_id, scheduled_for=None)

    evidence: dict[str, Any] = {}
    cleaned = 0
    try:

        def enqueue() -> dict[str, Any]:
            # Each in its OWN committed transaction, so the second meets a row
            # that is really there rather than one its own session holds open.
            with engine.begin() as connection:
                return enqueue_job(
                    connection=connection,
                    organization_id=organization_id,
                    job_id=identity["job_id"],
                    idempotency_key=identity["idempotency_key"],
                    source_id=source_id,
                    schedule_key=identity["schedule_key"],
                    # A member of CREATED_BY_RUNTIMES. This row IS a
                    # fixture written to verify a lane;
                    # `operator_enqueue` would claim an operator queued
                    # real work. An invented value is refused outright,
                    # which failed three conditions for one unrelated
                    # reason.
                    created_by_runtime="verifier_fixture",
                    now=now,
                )

        first = enqueue()
        duplicate = enqueue()

        # A genuinely new connection. This is the evidence a request cannot
        # produce, and the reason this lane cannot run inside a savepoint.
        with engine.connect() as connection:
            listed = list_jobs(
                connection=connection,
                organization_id=organization_id,
                source_id=source_id,
            )
        reread = dict(listed)
        reread["job"] = (listed.get("jobs") or [None])[0]

        with engine.begin() as connection:
            illegal = transition_job(
                connection=connection,
                organization_id=organization_id,
                job_id=identity["job_id"],
                to_status=REFUSED,
                terminal_reason="terms_blocked",
                now=now,
            )

        with engine.connect() as connection:
            backlog = count_backlog(
                connection=connection, organization_id=organization_id
            )

        evidence = {
            "enqueue_created": bool(first.get("created")),
            "duplicate_deduplicated": bool(duplicate.get("deduplicated")),
            "reread_on_a_new_connection": reread.get("job") is not None,
            "illegal_transition_reasons": illegal.get("blocked_reasons"),
            "backlog_completed_total": backlog.get("completed_total"),
            "backlog_rows_with_execution_proof": backlog.get(
                "rows_with_execution_proof"
            ),
            "table_exists_was_measured": True,
        }

        health = build_job_store_health(
            table_exists=_table_exists(engine, "nf_source_collection_jobs"),
            enqueue_result=first,
            duplicate_enqueue_result=duplicate,
            reread_after_reconnect=reread,
            illegal_transition_result=illegal,
            backlog=backlog,
        )
        failures = job_store_health_invariant_failures(health)
        conditions, unmet = _conditions_of(health)
        ready = bool(health.get("collection_job_store_ready")) and not failures
        exercised = True
    except Exception as exc:  # noqa: BLE001 - an unexercisable lane is not ready
        # Recorded, NOT returned. Returning here built the result before
        # `finally` computed `cleaned`, so a failing lane reported
        # cleanup_count 0 while cleanup had run - a number that read the same
        # whether or not anything was cleaned.
        raised = f"lane_raised:{type(exc).__name__}:{exc}"
        conditions, unmet, ready, failures = {}, [raised], False, []
        exercised = False
    finally:
        try:
            with engine.begin() as connection:
                cleaned = int(
                    connection.execute(
                        sa.text(
                            "DELETE FROM nf_source_collection_jobs "
                            "WHERE source_id LIKE :pattern"
                        ),
                        {"pattern": f"{FIXTURE_PREFIX}{stamp}.jobstore%"},
                    ).rowcount
                    or 0
                )
        except Exception:  # noqa: BLE001
            cleaned = -1

    return _lane(
        JOB_STORE_LANE,
        exercised=exercised,
        ready=ready,
        conditions=conditions,
        unmet=list(unmet) + [f"invariant:{f}" for f in failures],
        evidence=evidence,
        cleanup_count=cleaned,
    )


# ------------------------------------------------------------ lane 3
def _exercise_payloads(
    *, engine: Any, organization_id: Any, stamp: str, now: dt.datetime
) -> dict[str, Any]:
    """Write, read back, replay, refuse a conflict and an oversize, archive, tamper."""
    import sqlalchemy as sa

    from nativeforge.repositories.source_collection_raw_payload_repository import (
        MAX_PAYLOAD_BYTES,
        archive_payload,
        count_payloads,
        get_payload,
    )
    from nativeforge.services.source_collection_attempt_identity_service import (
        build_attempt_identity,
    )
    from nativeforge.services.source_raw_payload_health_service import (
        build_raw_payload_health,
        raw_payload_health_invariant_failures,
    )
    from nativeforge.services.source_raw_payload_persistence_service import (
        persist_raw_payload,
    )
    from nativeforge.services.source_raw_payload_replay_service import (
        replay_payload,
    )

    job_id = f"{FIXTURE_PREFIX}{stamp}.payload.job"
    source_id = f"{FIXTURE_PREFIX}{stamp}.payload"

    evidence: dict[str, Any] = {}
    cleaned = 0
    try:

        def write(attempt: int, body: bytes) -> dict[str, Any]:
            identity = build_attempt_identity(
                job_id=job_id, source_id=source_id, attempt_number=attempt
            )
            with engine.begin() as connection:
                # Hermetic: `collector_invoked` and `live_fetch_performed` stay
                # 0, so these rows are never counted by
                # `unauthorized_live_rows` however many are written.
                return persist_raw_payload(
                    connection=connection,
                    organization_id=organization_id,
                    job_id=identity["job_id"],
                    source_id=identity["source_id"],
                    attempt_number=identity["attempt_number"],
                    body=body,
                    response_headers=PROBE_HEADERS,
                    response_status=200,
                    received_at=now,
                )

        written = write(1, PROBE_BODY)

        with engine.connect() as connection:
            read = get_payload(
                connection=connection,
                organization_id=organization_id,
                attempt_id=written["attempt_id"],
                include_body=True,
            )
        round_tripped = read.get("body_bytes") == PROBE_BODY

        with engine.connect() as connection:
            replayed = replay_payload(
                connection=connection,
                organization_id=organization_id,
                attempt_id=written["attempt_id"],
            )

        # Same attempt, different bytes. Must be refused.
        conflict = write(1, PROBE_BODY + b"different")
        # Over the cap. Must be refused.
        oversize = write(2, b"x" * (MAX_PAYLOAD_BYTES + 1))

        archived_written = write(3, PROBE_BODY + b" third")
        with engine.begin() as connection:
            archive_payload(
                connection=connection,
                organization_id=organization_id,
                attempt_id=archived_written["attempt_id"],
                now=now,
            )
        with engine.connect() as connection:
            archived_replay = replay_payload(
                connection=connection,
                organization_id=organization_id,
                attempt_id=archived_written["attempt_id"],
            )

        # Corrupt a row this lane created, and prove the replay notices.
        tamper_target = write(4, PROBE_BODY + b" fourth")
        with engine.begin() as connection:
            connection.execute(
                sa.text(
                    "UPDATE nf_source_collection_raw_payloads "
                    "SET body_bytes = :body WHERE attempt_id = :attempt"
                ),
                {"body": b"tampered", "attempt": tamper_target["attempt_id"]},
            )
        with engine.connect() as connection:
            tampered = replay_payload(
                connection=connection,
                organization_id=organization_id,
                attempt_id=tamper_target["attempt_id"],
            )

        with engine.connect() as connection:
            counts = count_payloads(
                connection=connection, organization_id=organization_id
            )

        evidence = {
            "bytes_round_tripped": bool(round_tripped),
            "conflict_refused": not conflict.get("persisted"),
            "oversize_refused": not oversize.get("persisted"),
            "tamper_detected": bool(tampered.get("tamper_detected"))
            or not bool(tampered.get("hash_verified")),
            # What the health builder actually reads: archived AND replayable.
            "archived_still_readable": bool(
                archived_replay.get("archived") and archived_replay.get("replayable")
            ),
            "unauthorized_live_rows": counts.get("unauthorized_live_rows"),
            "rows_written": 3,
            "table_exists_was_measured": True,
        }

        health = build_raw_payload_health(
            table_exists=_table_exists(engine, "nf_source_collection_raw_payloads"),
            write_result=written,
            replay_result=replayed,
            tamper_result=tampered,
            conflict_result=conflict,
            metadata_result=written.get("metadata"),
            oversize_result=oversize,
            archived_replay_result={
                **archived_replay,
                "archived": archived_replay.get("archived"),
            },
            counts=counts,
            bytes_round_tripped=round_tripped,
        )
        failures = raw_payload_health_invariant_failures(health)
        conditions, unmet = _conditions_of(health)
        ready = bool(health.get("raw_payload_persistence_ready")) and not failures
        exercised = True
    except Exception as exc:  # noqa: BLE001 - an unexercisable lane is not ready
        # Recorded, NOT returned. Returning here built the result before
        # `finally` computed `cleaned`, so a failing lane reported
        # cleanup_count 0 while cleanup had run - a number that read the same
        # whether or not anything was cleaned.
        raised = f"lane_raised:{type(exc).__name__}:{exc}"
        conditions, unmet, ready, failures = {}, [raised], False, []
        exercised = False
    finally:
        try:
            with engine.begin() as connection:
                cleaned = int(
                    connection.execute(
                        sa.text(
                            "DELETE FROM nf_source_collection_raw_payloads "
                            "WHERE source_id LIKE :pattern"
                        ),
                        {"pattern": f"{FIXTURE_PREFIX}{stamp}.payload%"},
                    ).rowcount
                    or 0
                )
        except Exception:  # noqa: BLE001
            cleaned = -1

    return _lane(
        PAYLOAD_LANE,
        exercised=exercised,
        ready=ready,
        conditions=conditions,
        unmet=list(unmet) + [f"invariant:{f}" for f in failures],
        evidence=evidence,
        cleanup_count=cleaned,
    )


# ------------------------------------------------------------ the exerciser
def exercise_runtime_lanes(
    *,
    connection: Any = None,
    organization_id: Any = None,
    now: Any = None,
    engine: Any = None,
    stamp: Any = None,
) -> dict[str, Any]:
    """Exercise the four required lanes and report what each one measured.

    `connection` is the caller's, used for the lane that reads rather than
    writes. The probe writes need their own committed connections, which is
    what `engine` is for; it defaults to the application engine.
    """
    import sqlalchemy as sa

    run_stamp = str(stamp or uuid.uuid4().hex[:10])
    moment = now or dt.datetime.now(dt.UTC)
    if isinstance(moment, str):
        moment = dt.datetime.fromisoformat(moment.replace("Z", "+00:00"))

    if engine is None:
        try:
            from nativeforge.db.session import engine as app_engine

            engine = app_engine
        except Exception as exc:  # noqa: BLE001
            return _result(
                lanes=[
                    _lane(
                        name,
                        exercised=False,
                        ready=False,
                        unmet=[f"no_engine:{type(exc).__name__}"],
                    )
                    for name in REQUIRED_LANES
                ],
                stamp=run_stamp,
                residue=-1,
            )

    lanes = [
        _observe_envelope(connection=connection, organization_id=organization_id),
        _exercise_worker(
            engine=engine,
            organization_id=organization_id,
            stamp=run_stamp,
            now=moment,
        ),
        _exercise_job_store(
            engine=engine,
            organization_id=organization_id,
            stamp=run_stamp,
            now=moment,
        ),
        _exercise_payloads(
            engine=engine,
            organization_id=organization_id,
            stamp=run_stamp,
            now=moment,
        ),
    ]

    # Residue, counted rather than assumed. A cleanup that reports success
    # without counting rows is the same defect as a readiness flag nobody
    # measured.
    residue = 0
    try:
        with engine.connect() as probe:
            for table, column in (
                ("nf_source_collection_raw_payloads", "source_id"),
                ("nf_source_collection_jobs", "source_id"),
                ("nf_source_collection_job_leases", "job_id"),
            ):
                residue += int(
                    probe.execute(
                        sa.text(
                            f"SELECT count(*) FROM {table} "  # noqa: S608
                            f"WHERE {column} LIKE :pattern"
                        ),
                        {"pattern": f"{FIXTURE_PREFIX}{run_stamp}%"},
                    ).scalar()
                    or 0
                )
    except Exception:  # noqa: BLE001
        residue = -1

    return _result(lanes=lanes, stamp=run_stamp, residue=residue)


def _result(*, lanes: list[dict[str, Any]], stamp: str, residue: int) -> dict[str, Any]:
    by_name = {lane["lane_name"]: lane for lane in lanes}
    unmet_lanes = sorted(
        name for name in REQUIRED_LANES if not by_name.get(name, {}).get("ready")
    )
    all_ready = not unmet_lanes

    # The failed CONDITION, named, not just the failed lane. "not_ready" with
    # nothing named is the shape an operator cannot act on.
    unmet_conditions: list[str] = []
    for name in unmet_lanes:
        for condition in by_name.get(name, {}).get("unmet_conditions") or []:
            unmet_conditions.append(f"{name}:{condition}")

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "scope": CONTROLLED_SCOPE,
            "fixture_prefix": FIXTURE_PREFIX,
            "run_stamp": stamp,
            "lanes": by_name,
            "lane_names": list(REQUIRED_LANES),
            "required_lanes": list(REQUIRED_LANES),
            "runtime_status": READY if all_ready else NOT_READY,
            "all_required_lanes_ready": all_ready,
            "unmet_lanes": unmet_lanes,
            "unmet_conditions": sorted(unmet_conditions),
            "lanes_exercised": sum(1 for lane in lanes if lane["exercised"]),
            "fixture_rows_cleaned": sum(
                max(lane["cleanup_count"], 0) for lane in lanes
            ),
            "cleanup_failures": sorted(
                lane["lane_name"] for lane in lanes if lane["cleanup_count"] < 0
            ),
            "fixture_residue": residue,
            "measured_at_dispatch_time": True,
            "is_a_stored_claim": False,
            "not_implied": list(NOT_IMPLIED),
        }
    )


def exerciser_invariant_failures(result: dict[str, Any]) -> list[str]:
    """Refuse an exerciser result that contradicts itself or leaves residue."""
    fails: list[str] = []

    if result.get("schema_version") != SCHEMA_VERSION:
        fails.append("schema_version_mismatch")
    if result.get("is_a_stored_claim") is not False:
        fails.append("readiness_became_a_stored_claim")

    ready = bool(result.get("all_required_lanes_ready"))
    status = str(result.get("runtime_status") or "")
    if ready and status != READY:
        fails.append("all_lanes_ready_but_status_is_not_ready")
    if not ready and status != NOT_READY:
        fails.append("a_lane_failed_but_status_is_ready")

    # ready and unmet must agree, both directions.
    unmet_lanes = list(result.get("unmet_lanes") or [])
    if ready and unmet_lanes:
        fails.append(f"ready_alongside_unmet_lanes:{unmet_lanes}")
    if not ready and not unmet_lanes:
        fails.append("not_ready_without_naming_a_lane")
    if unmet_lanes and not result.get("unmet_conditions"):
        fails.append("a_lane_failed_without_naming_a_condition")

    lanes = result.get("lanes") or {}
    if set(lanes) != set(REQUIRED_LANES):
        fails.append("lanes_do_not_match_the_required_set")
    for name in REQUIRED_LANES:
        lane = lanes.get(name) or {}
        if lane.get("ready") and lane.get("unmet_conditions"):
            fails.append(f"lane_ready_with_unmet_conditions:{name}")
        if lane.get("ready") and not lane.get("exercised"):
            fails.append(f"lane_ready_without_being_exercised:{name}")

    # Residue is a failure whatever the lanes said.
    residue = int(
        result.get("fixture_residue")
        if result.get("fixture_residue") is not None
        else -1
    )
    if residue > 0:
        fails.append(f"fixture_residue:{residue}")
    if residue < 0:
        fails.append("fixture_residue_could_not_be_counted")
    if result.get("cleanup_failures"):
        fails.append(f"cleanup_failed:{result.get('cleanup_failures')}")

    return sorted(set(fails))
