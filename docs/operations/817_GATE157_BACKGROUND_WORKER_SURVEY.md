# 817 — Gate 157: what a worker needs that this repository does not have

Read-only survey. Every claim below was measured by reading the code or the
schema it describes.

## The worker that exists

`source_scheduler_dry_run_worker_service.run_dry_run_worker` (Gate 100C) takes a
queue or a list of jobs, classifies each one, and returns outcomes. Its own
docstring is accurate about what it is:

> A dry-run worker is not a worker. It is the shape a worker would have,
> exercised against jobs that cannot run.

Measured against it, by grep and by reading every function:

```text
worker identity      absent   no worker_id anywhere
job claiming         absent   nothing records that a worker touched a job
lease semantics      absent   no owner, no acquired_at, no expires_at
retry accounting     absent   no attempt count, no next-retry time
failure classes      absent   outcomes are blocked/skipped, not why
persistence          absent   everything is an in-memory list
restart recovery     absent   there is nothing to recover
a process            absent   no python entrypoint runs it
```

It is a pure function over a list. That is the correct shape for Gate 100 and it
is not a worker runtime.

## Can two workers race today?

Yes, trivially — and not because of a bug. Nothing records that a worker looked
at a job, so two processes calling `run_dry_run_worker` on the same queue both
classify every job and neither can tell. It does not matter today because the
classification writes nothing; it matters the moment a worker does anything.

**Claiming is the component Gate 157 exists to add.**

## Is there a table that could hold a lease?

Four candidates carry job-ish or run-ish names. None has lease semantics:

```text
nf_discovery_intake_runs   a discovery intake that ran, with counts
nf_nofo_extraction_runs    extraction output
nf_pursuit_tasks           human tasks on a pursuit, with due_at
nf_source_check_runs       a source check that ran
```

`nf_source_check_runs` is the closest and the one most likely to be misused. Its
`check_status` vocabulary is, measured from `SourceCheckRunStatus`:

```text
scheduled  running  succeeded  succeeded_with_warnings  failed  canceled
```

That is the lifecycle of **a check that is happening or has happened**, with
columns for `opportunities_seen_count`, `new_candidates_count` and
`accepted_count` beside it. Writing a lease row there would assert that a check
ran when nothing did — fabricating evidence in a table other gates read.

Gate 157C's own rule: *do not silently reuse unrelated generic job tables unless
schema semantics match.* They do not match, and the mismatch is not cosmetic.

**So a migration is genuinely required**, and it is the first in this block:
`0043_nf_source_collection_job_leases`. Gate 156 avoided one by reusing
`nf_opportunity_sources`, which already had the scheduling columns; there is no
equivalent here.

## What the scheduler hands over

Gate 156's `run_scheduler_cycle` returns jobs carrying:

```text
job_id  source_id  runtime_state  due  executable  blockers  next_run_at
activation_state  terms_state  human_review_state  collector_registered
```

`executable` is the field that matters: it is true only when every prerequisite
is affirmatively the permitting value. Today it is false for all 177 sources.

A worker consuming these must **not** re-derive permission. The scheduler
already decided; a worker that recomputed it would be a second place for the
answer to live, which is how two places come to disagree.

## Retries: the distinction nothing currently makes

Gate 100C classifies a job as blocked and stops. A worker needs to know whether
a failure is worth trying again, and the categories are not interchangeable:

```text
refused_by_activation      NOT a retry. No approval exists. Trying again in
                           five minutes changes nothing, and a retry queue
                           full of unapprovable jobs hides the real backlog.
terms_blocked              NOT a retry. A human must read the terms.
human_review_blocked       NOT a retry. A human must look.
transient_worker_failure   retry, bounded, with backoff.
permanent_worker_failure   NOT a retry. Something is wrong with the handler.
```

Treating an activation refusal as a transient failure is the defect this gate is
most likely to introduce: it would produce a worker that appears busy, burns
attempts, and never tells anyone that 171 sources need a human.

## What exists for process running

```text
scripts/*.py            11 one-shot scripts. None is a worker loop.
ops/systemd/            3 units: cloudflared, demo-preview, mayhem-tunnel.
                        No worker unit, no .timer.
console_scripts         no nativeforge worker or scheduler entry point
```

Gate 98E's `detect_background_worker` looks for `nativeforge.workers`,
`nativeforge.worker`, `nativeforge.scheduler`, `nativeforge.tasks`,
`nativeforge.jobs` and for a console entry point. All absent, which is why
`background_worker_available` is false.

## What Gate 157 builds

```text
a lease service    atomic claim, owner, acquired_at, expires_at. A duplicate
                   claim is refused; an EXPIRED lease can be reclaimed; a live
                   one cannot be stolen.
a retry policy     bounded attempts, deterministic backoff, and five failure
                   classes of which only one retries.
a worker runtime   one cycle, injectable clock, explicit worker_id, no threads.
a migration        0043, leases only - no bodies, no credentials, no customer
                   data.
a process          scripts/run_source_collection_worker.py, one-shot by
                   default, with an opt-in loop.
health             worker_runtime_ready, and source_monitoring_live still false.
```

## What it will not do

It invokes no collector, opens no socket, and needs no credential. With zero
approved sources the scheduler marks every job non-executable, so the worker's
own refusal path is the only path any of the 177 can take.

**A worker that can claim a job it is never allowed to run is still a worker.**
It is just honest about having nothing to do.
