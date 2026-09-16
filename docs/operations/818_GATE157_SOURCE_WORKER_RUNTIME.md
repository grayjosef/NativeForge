# 818 — Gate 157: the source collection worker runtime

```text
worker_runtime_ready     true
source_monitoring_live   false
jobs offered             177
jobs claimed             177
jobs refused             177
jobs completed           0
collectors invoked       0
live source calls        0
```

## What Gate 100C already had, and what it lacked

`source_scheduler_dry_run_worker_service.run_dry_run_worker` classifies a list
of jobs and returns outcomes. Its own docstring is accurate: *"a dry-run worker
is not a worker"*. Measured against it:

```text
worker identity   absent      job claiming     absent
lease semantics   absent      retry accounting absent
failure classes   absent      persistence      absent
restart recovery  absent      a process        absent
```

Two workers could race trivially, because nothing recorded that either had
looked at a job. It did not matter while the classification wrote nothing; it
matters the moment a worker does anything.

## What this gate added

```text
identity    an explicit worker_id on every claim and every outcome
claiming    an atomic lease, refused when another worker holds one
retries     bounded, classified, persisted so a crash cannot reset them
recovery    the lease table IS the state; a restarted worker reads it
a process   scripts/run_source_collection_worker.py, one-shot by default
```

## It does not re-derive permission

Gate 156's scheduler already decided `executable` from activation, terms, human
review, a collector and the clock. This worker **reads** that decision.

A worker that recomputed permission would be a second place for the answer to
live, and two places is how they come to disagree — the defect found in a
delivery guard at Gate 152 and in a next-action constant at Gate 154.

## A refusal is not a failure

With zero approved sources every job is refused, and that is the worker working:

```text
it claimed the job              took responsibility for deciding
it asked whether it may run it  read the scheduler's verdict
it was told no                  by all 177 sources
it recorded the reason          terms_blocked, on the row
it released the claim           the next worker is not blocked
```

`jobs_completed` is 0 and an invariant fails if it is ever anything else. A
completed job in Gate 157 would mean something ran, and no handler exists.

## The batch limit is visible

`jobs_offered`, `jobs_seen` and `jobs_not_reached_this_cycle` must add up, and
an invariant checks it. A first run silently truncated 177 to 100 at the default
cap — a batch limit is reasonable, a batch limit nobody can see is how a backlog
goes unnoticed.

## The process

```bash
python scripts/run_source_collection_worker.py --once
python scripts/run_source_collection_worker.py --loop --interval 60 --max-cycles 3
```

One-shot is the default. `--loop` is bounded by `--max-cycles`; **there is no
unbounded mode**, and a test asserts `while True` does not appear in the file.

Arguments are counts, intervals, a worker id and flags. No token, no URL, no
credential — a test asserts `--token`, `--api-key`, `--password` and `--secret`
are absent.

SIGINT and SIGTERM let the current cycle finish. A worker killed mid-cycle
leaves its lease behind, which is exactly what expiry is for.

## No systemd unit was installed

157F permits one. None was created and none enabled: the worker has nothing to
do, and a unit that restarts a process whose only output is a log line is a
process somebody has to remember to stop. Gate 159 owns triggers.

## The detector this gate does not satisfy

Gate 98E's `detect_background_worker` looks for a `nativeforge.workers`,
`nativeforge.worker`, `nativeforge.scheduler`, `nativeforge.tasks` or
`nativeforge.jobs` module, or a console entry point. This gate adds a **script**,
so `background_worker_available` stays false and Gate 143 keeps listing
`scheduler_component_absent:background_worker`.

The same shape as Gate 156 and the scheduler package: a detector looking for a
package is not a measure of capability, and satisfying the detector without
building the capability would be the wrong trade.

## Routes

```text
GET  /v1/nf/demo/orgs/{org}/source-worker/health
GET  /v1/nf/demo/orgs/{org}/source-worker/jobs
GET  /v1/nf/demo/orgs/{org}/source-worker/leases
POST /v1/nf/demo/orgs/{org}/source-worker/dry-run
```

The POST passes **no connection**, so the worker runtime refuses outright and no
lease is taken. That is what makes it safe rather than merely intended: claiming
a lease from a request would take a claim a real worker then could not have,
released only by expiry.

The leases GET returns rows as they are, including stale ones. Nothing here
expires, releases or reclaims — a sweeper is a scheduled job.
