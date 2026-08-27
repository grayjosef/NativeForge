# 556 — Gate 99C: dry-run queue contract

`src/nativeforge/services/source_scheduler_queue_service.py`
`scripts/run_nativeforge_source_scheduler_dry_run.py`

Turns Gate 98B schedule decisions into a queue of jobs. It builds records and
nothing consumes them.

## A dry-run queue is not monitoring

This is the sentence the gate turns on. After this service exists the repository
can produce a list of work that *would* be done. Nothing dispatches it, no
request goes out, and no source is being watched.

```text
jobs_dispatched         0
collectors_executed     false
live_fetch_performed    false
raw_payloads_written    false
source_monitoring_live  false
live_source_coverage    false
live_jobs_created       0
```

Every one is held by an invariant, and the module imports no HTTP client, no
collector, no fetcher and no body store — checked by parsing its AST rather than
by grepping its text.

## What the queue does today

Run against the five Phase 1 sources with the state they actually have:

```text
decisions considered   5
jobs_total             5
jobs_queued            0
jobs_blocked           5
jobs_deduplicated      0
live_jobs_created      0

blocked reasons across the queue:
  activation_not_allowed:activation_blocked
  circuit_does_not_permit:unknown
  production_payload_store_unavailable:unavailable
  schedule_does_not_permit_enqueue:unknown
```

Every source is blocked. No Phase 1 source has ever been checked, so none has a
`next_check_due_at`, and Gate 98B reports `unknown` rather than treating an
absent schedule as a licence to run now. On top of that no production raw payload
store exists, so a check would have nowhere durable to put what came back.

## Blocked sources stay in the queue

A source that cannot be checked is queued as a `blocked` job carrying its
reasons, not dropped. An operator reading this queue needs to see the sources
that are stuck, not only the ones that are fine — a queue listing only the
workable sources would look healthy by omission.

Sources with genuinely nothing to do — `not_due`, `disabled` — are not queued at
all, and are counted separately as `decisions_not_queueable`. There is a
difference between "blocked" and "nothing to do", and collapsing them would make
the blocked count meaningless.

## Deduplication and order independence

Two decisions describing the same work produce one job. Jobs are sorted by
idempotency key — a hash, so stable across runs and independent of input order —
and the first occurrence wins. Duplicates are counted, not silently discarded.

An invariant re-derives `queue_id` from the queue's own contents, so a queue
whose jobs were edited after the fact fails rather than passes. A test reverses
the decision list and asserts the same `queue_id` and the same job order.

## The live flag exists and changes nothing

`build_dry_run_queue` takes `allow_live_collection`, defaulting to False. Set
True, the queue still produces zero live jobs: the job model requires a
background worker, Gate 98E detects none, and `live_jobs_created` is counted
**from the jobs actually built** rather than from what was requested.

That distinction was worth testing directly. A mutation replacing the count with
a constant empty list survived every other test in the file, because zero is the
only answer the system can currently produce. There is now a test that forces a
live job through the queue and asserts the count follows it.

## The CLI

`scripts/run_nativeforge_source_scheduler_dry_run.py`, mode 755, following the
existing `scripts/*.py` convention Gate 99A surveyed.

```text
exit 0   a dry-run queue was built and reported
exit 2   a live_collection job was created - refused
exit 3   the queue or readiness failed its own invariants
```

The live check runs first so its specific message wins, and it counts the jobs
rather than reading the requested mode — a request is an intention, and the jobs
are the fact.

Three tests cover it: it exits zero doing no live work, it exits 2 when a live
job is forced into the bundle, and it runs to completion in-process with
`socket.connect` and `socket.create_connection` poisoned to raise. A fourth
checks its output for credential markers.

`--write-artifacts` regenerates `artifacts/source_scheduler_dry_run/`.
`--json` prints the queue summary, which carries counts and no job bodies.
