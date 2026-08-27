# 555 — Gate 99B: source job model contract

`src/nativeforge/services/source_scheduler_job_model_service.py`

A job is a description of work. Building one performs no network I/O, invokes no
collector, and writes nothing.

## No collectors executed, no live fetch, no raw payloads

```text
executed                false
fetch_performed         false
collector_invoked       false
raw_payload_written     false
source_monitoring_live  false
```

All five are constants on every job and all five are held by invariants. The
module imports no HTTP client, no collector, and no body store, and a test parses
its AST to prove it — a service that decides whether to fetch must not be able to
fetch.

## Vocabularies

```text
job_type         source_check, forecast_lapse_check, amendment_check,
                 raw_payload_reconciliation, terms_review_recheck
execution_mode   dry_run, live_collection, replay_fixture, manual_review
job_status       queued, blocked, skipped, running, completed, failed, cancelled
```

`dry_run` is the default. An unrecognised mode falls back to `dry_run` and an
unrecognised job type falls back to `source_check`; neither is an error, and
neither opens anything.

Three of the seven statuses — `running`, `completed`, `failed` — describe
execution. Nothing in this gate executes, so an invariant fails any job holding
one. That is stricter than it needs to be today and it is the point: the status
vocabulary is the one a real worker will use, and the invariant is what stops a
worker being wired up without anyone noticing the boundary moved.

## live_collection has to be earned, and today it cannot be

`live_collection` is not refused outright — a permanent refusal would make this
module useless the day a worker exists. It is granted only when every
precondition is affirmatively satisfied:

```text
activation_allowed           activation_status == activation_allowed
schedule_permits_enqueue     due_and_safe_to_enqueue
circuit_permits              closed or half_open
production_payload_store     production_available
background_worker_available  detected via Gate 98E
```

Each is a membership test against a satisfying set. Nothing is subtracted from a
permissive default — the Gate 79B rule, still the one that matters most here.

The fifth is why `live_jobs_created` is zero in this gate, and it is a
*derivation* rather than a constant. Gate 98E detects that no background worker
exists, so a live request downgrades. When a worker does exist, this stops
downgrading on its own, rather than waiting for somebody to remember.

A downgraded request is recorded, not silently honoured:

```text
requested_execution_mode  live_collection
execution_mode            dry_run
blocked_reasons           live_collection_downgraded,
                          background_worker_unavailable
```

Never an error, and never a live job that "probably would have been fine".

## Deterministic identity

```text
job_id           sha256(source, collector, job_type, scheduled_for, execution_mode)
idempotency_key  sha256(source, collector, job_type, scheduled_for)
```

Neither includes `created_at`. Including a wall clock would make every
description of the same job unique, which is exactly the bug deduplication exists
to prevent — and would make the committed artifacts differ on every run.

The key excludes execution mode and attempt number, because a retry of a job, and
a dry rehearsal of a job that would later run live, are the same *piece of work*.
That is what lets the queue deduplicate without a database.

Both are re-derived inside `job_invariant_failures` from the job's own fields, so
a record whose identity was edited after the fact fails rather than passes.

## Blocked jobs state why

A job that cannot run is kept with `blocked_reasons` populated, and an invariant
fails a blocked job carrying no reason as well as a job carrying reasons that
still reads `queued`. Dropping blocked jobs would make a queue look healthy by
omission — the same shape as a check-run count with no payload behind it, which
Gate 98D exists to prevent.

## No table, and no migration

Gate 99A found no job or queue table anywhere in `db/models.py`. This is a
contract over values, in the shape of Gates 95–98. A durable job table is a real
decision with a schema and a retention policy behind it, and it belongs to
whichever gate actually deploys a worker.
