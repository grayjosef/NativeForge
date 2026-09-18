# 848 — Gate 163T: what the existing runtime-lane exercises actually do

Survey before implementation. `runtime_status` must come from fresh in-process
evidence, so the question is which operations genuinely produce that evidence
and which are verifier ceremony that a dispatch path has no business running.

Four lanes are required for collection:

```text
worker_runtime_ready
collection_job_store_ready
raw_payload_persistence_ready
collector_execution_envelope_ready
```

## Lane 4 needs no exercise at all

`collector_execution_envelope_ready` is the exception worth finding first.
`build_execution_health(connection=..., organization_id=...)` reads the attempt
table itself and already reports ready. It writes nothing, needs no fixture,
and is the one lane whose health builder does its own measuring.

Measured cold, with a connection: **ready**. Zero fixture rows.

Everything below is about the other three.

## Why a savepoint cannot carry this

`collection_job_store_ready` requires `survives_restart`:

> a row written by one connection was read back by another after the first
> one was gone

That is the whole point of the condition, and it cannot be produced inside a
transaction that is later rolled back — an uncommitted row is invisible to a
second connection by definition. `_g158_phase_health.py` says so in its own
docstring: the health route "deliberately supplies no restart evidence, because
proving a row survives a restart needs a commit and a reconnect".

So the exerciser must **commit**, and therefore must clean up explicitly after
its last probe write. A savepoint is not an option for this lane, and using one
would quietly turn `survives_restart` into a condition nothing measures.

## Lane 1 — worker runtime

`build_worker_health` wants four pieces of evidence:

| evidence | how it is produced | writes |
| --- | --- | --- |
| `cycle` | `run_worker_cycle(...)` over supplied jobs | job transitions |
| `duplicate_claim_refused` | `claim_job` twice, same job, two workers, one clock | 1 lease row |
| `expired_lease_reclaimed` | `claim_job` again at a later clock | updates that row |
| `retry_bounded` | `evaluate_retry(TRANSIENT, attempt_count=3, max_attempts=3)` | none — pure |

`retry_bounded` needs no database at all. The two claim probes share one lease
row in `nf_source_collection_job_leases`.

### Verifier-only ceremony in this lane

The Gate 157 verifier also runs the full blocker-classification matrix, the
retry matrix across four failure classes, the "every refusal condition fires
alone" set, the completed-job and retryable-job guard probes, and a comparison
against `build_scheduler_readiness`. None of it feeds `worker_runtime_ready`.
It is testing the worker's decision logic, which is a different question from
"can the worker operate right now".

### One thing in this lane is actively unsafe to reuse

```python
# Clean slate. Deleted by ORGANIZATION, not by a job_id prefix
DELETE FROM nf_source_collection_job_leases WHERE organization_id = :o
```

Correct for a verifier that owns the demo org for the duration of its run.
Wrong for a dispatch path: it would delete lease rows the exerciser did not
create. The exerciser cleans up **by its own fixture ids** and never by
organization.

## Lane 2 — collection job store

`build_job_store_health` wants:

| evidence | how it is produced | writes |
| --- | --- | --- |
| `table_exists` | passed as the literal `True` | — |
| `enqueue_result` | `enqueue_job` in a committed transaction | 1 job row |
| `duplicate_enqueue_result` | the same enqueue again, separately committed | 0 (dedups) |
| `reread_after_reconnect` | `list_jobs` on a **new** connection | none |
| `illegal_transition_result` | `transition_job` queued → refused | none (refused) |
| `backlog` | `count_backlog` | none |

One fixture job row. The second enqueue must be its own committed transaction
so it meets a row that is really there rather than one its own session is
holding open.

## Lane 3 — raw payload persistence

The heaviest. `build_raw_payload_health` wants ten pieces:

| evidence | how it is produced | rows |
| --- | --- | --- |
| `table_exists` | passed as the literal `True` | — |
| `write_result` | `persist_raw_payload` attempt 1 | 1 |
| `bytes_round_tripped` | `get_payload(include_body=True)` compared to the bytes | — |
| `replay_result` | `replay_payload` | — |
| `conflict_result` | attempt 1 again with different bytes → refused | 0 |
| `oversize_result` | attempt 2 over `MAX_PAYLOAD_BYTES` → refused | 0 |
| `archived_replay_result` | attempt 3, `archive_payload`, replay | 1 |
| `tamper_result` | attempt 4, raw `UPDATE body_bytes`, replay | 1 |
| `metadata_result` | `write_result["metadata"]` — safe headers kept, secrets refused | — |
| `counts` | `count_payloads` | — |

Three rows survive to be cleaned up; the conflict and oversize writes are
refused and leave nothing.

The header set is part of the evidence, not decoration: it deliberately
includes `Authorization`, `Cookie`, `Set-Cookie` and `X-API-Key` so
`secret_headers_refused` has something to refuse, alongside safe headers so
`safe_headers_survive` has something to keep.

### These writes do not create unauthorized live rows

Worth stating because it would otherwise be the first thing to worry about.
`unauthorized_live_rows` counts rows where

```sql
(live_fetch_performed = 1 OR collector_invoked = 1)
AND authorized_source_id IS NULL
```

The exerciser's payloads are hermetic: both flags stay 0, so the rows are not
counted however many are written. Confirmed against the live database, which
currently holds one payload row (the authorized robots evidence) and reports
`unauthorized_live_rows = 0`.

## Two declared values that should be measured

`table_exists=True` is passed as a literal in both `_g158_phase_health.py` and
`_g160_phase_health.py`. It is true, and it is not measured — the same
declared-versus-derived shape this campaign keeps finding. The exerciser reads
the schema instead, so a missing table reports as a missing table rather than
as some later condition failing for an unexplained reason.

## Fixture namespace and cleanup

```text
lane 1  nf163.exercise.<stamp>.worker    1 lease row, job transitions
lane 2  nf163.exercise.<stamp>.jobstore  1 job row
lane 3  nf163.exercise.<stamp>.payload   3 payload rows
lane 4  -                                nothing
```

A per-run stamp, so two concurrent exercises cannot collide on the unique
indexes the idempotency probes depend on. Cleanup runs after the last probe
write of every lane, deletes by those ids only, and counts what it removed —
because a cleanup that reports success without counting rows is the same defect
as a readiness flag nobody measured.

## What the exerciser must not do

Carried over from the gate constraints, and each one is a thing one of the
surveyed scripts does that a dispatch path must not:

- no `DELETE ... WHERE organization_id` — cleanup is by fixture id
- no source activation, opt-in or decision writes
- no job row for the collection itself; the lane-2 fixture job is the
  exerciser's own and is deleted, which is a different thing from the
  collection inventing a durable scheduler job to satisfy readiness
- no network, email or object store
- no real customer data, and the real org untouched
