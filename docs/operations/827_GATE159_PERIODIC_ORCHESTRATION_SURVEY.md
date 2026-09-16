# 827 — Gate 159: what wakes the scheduler, and what happens when two do

Read-only survey. Every value was measured by running the code it describes.

## Nothing wakes the scheduler

```text
systemd --user units installed    3
  nativeforge-backend.service          active   (FastAPI, loopback :8000)
  nativeforge-demo-preview.service     active   (stamped Vite, :5175)
  nativeforge-mayhem-tunnel.service    active   (cloudflared)

systemd --user timers for nativeforge    0
units in the repo for a scheduler/worker 0
```

`scripts/run_source_collection_worker.py` has a bounded `--loop --interval
--max-cycles`, and **nothing invokes it**. A cycle happens when a person runs a
command. That is the gap.

## The measurement that makes a periodic trigger safe

Gate 158's `job_id` digests `scheduled_for`, which is the scheduler's computed
`next_run_at`. If that value moved with the observer's clock, every poll would
mint a new id and the idempotency Gate 158 proved would be worthless the moment
anything polled.

It does not move:

```text
now=2026-09-16T12:00:00Z  next_run_at=2026-09-08T00:00:00+00:00
now=2026-09-16T12:00:01Z  next_run_at=2026-09-08T00:00:00+00:00
now=2026-09-16T18:44:13Z  next_run_at=2026-09-08T00:00:00+00:00
now=2026-09-17T03:00:00Z  next_run_at=2026-09-08T00:00:00+00:00
```

`next_run_at` is `last_checked_at + check_interval_days`, derived from stored
facts and not from `now`. So two orchestration cycles at different wall clocks
inside one window describe the *same slot*.

Measured end to end, two committed cycles 7.5 hours apart:

```text
cycle A   created=3  deduplicated=0
cycle B   created=0  deduplicated=3
job rows                          3
```

**Job-level idempotency already holds under repeated triggering.** Gate 159 does
not need to protect job rows. It needs to protect everything else.

## What is NOT protected

```text
protected already   duplicate job ROWS          Gate 158 unique index
protected already   duplicate CLAIMS on a job   Gate 157 unique index

NOT protected       two orchestration cycles running at once
NOT protected       the same trigger slot firing twice
NOT protected       any record that a cycle happened at all
NOT protected       a missed trigger slot after downtime
```

Two orchestrators today would both run a full scheduler pass, both enqueue (one
deduplicating), and both run a worker pass. The rows stay correct; the work is
duplicated, and nothing anywhere records that a cycle occurred or that a slot
was already served.

## Source schedules never advance, and that changes the design

```text
nf_opportunity_sources rows            40
rows with last_checked_at NULL          0
newest last_checked_at        2026-06-29 21:44:29
nf_source_check_runs rows               0
```

`last_checked_at` is roughly eleven weeks stale and nothing advances it, because
advancing it is what an actual source check does and no check has ever happened.
`nf_source_check_runs` is empty.

So **every source is permanently due, in a slot that never moves.** Two
consequences for this gate:

1. A "missed window" cannot be derived from source cadence. The source slot is
   the same slot it was in June, so there is no sequence of missed source
   windows to walk. **Missed windows must be derived from the orchestration
   trigger slot** — a wall clock cadence this gate owns — not from
   `next_run_at`.

2. The orchestrator **must not advance `last_checked_at`**. Writing it would
   assert that a check occurred, which is the `persisted job != execution` rule
   applied to schedule advancement. Gate 159 leaves it alone, which means every
   source stays due and the backlog stays visible.

## There is no locking primitive to compose

```text
grep for pg_advisory_lock, advisory_lock, FOR UPDATE, with_for_update in src/
  0 hits

tables with an owner + acquired_at + released_at shape, excluding the job lease
  none
tables naming an orchestration cycle
  none

database backend   sqlite+pysqlite
```

SQLite has no `pg_advisory_lock`, so an advisory lock is not portable here. The
portable atomic primitive is a **unique index**, which is exactly what Gate 157
used for the job lease and Gate 158 for enqueue idempotency.

So 159E does need a new table. It is not a duplicate of Gate 157: that lease is
per **job** and answers *who is working this one piece of work*; this one is per
**orchestration cycle** and answers *who is running the loop right now*. One
cycle covers every job in a pass.

## There is no period-slot builder to compose either

`digest_period_key` exists on `nf_tenant_digest_records` and in the digest
dry-run queue, but it is always **supplied by the caller** — nothing in the
repository computes a period key from a clock and a cadence. So trigger-slot
computation is genuinely new work rather than a second copy of something.

Noted while looking: `source_freshness_pilot_checker_service.py` reads
`datetime.now(UTC)` directly. Gate 159's trigger must take an injected clock, as
Gates 156–158 do, or the verifier cannot test a missed window without waiting
for one.

## Can a cycle be reconstructed today?

```text
did an orchestration cycle run?     unknowable - nothing records one
when is the next one due?           unknowable - no cadence exists
was this slot already served?       unknowable
did two cycles overlap?             unknowable
were any slots missed while down?   unknowable
who is running one right now?       unknowable
```

Every line is unknowable, which is what it looks like when the component is
absent rather than broken.

## The exact missing runtime component

```text
missing   a wall-clock orchestration cadence, and the slot arithmetic that
          turns an instant into a trigger slot
missing   a deterministic cycle identity over (cadence, slot), distinct from
          Gate 158's job_id
missing   a single-active-cycle ownership record with atomic acquisition
missing   bounded recovery of trigger slots missed during downtime
missing   a process that wakes, and a unit that supervises it
missing   a health lane that reports all of the above
```

## What Gate 159 will build

```text
a trigger service        deterministic slot, injected clock, 7 states
an identity service      cycle_id over (cadence, version, slot)
an ownership record      minimum semantics, unique index, expiry reclaim
missed-window recovery   bounded, deterministic, restart-idempotent
an orchestration runtime scheduler -> store -> worker, one report
a script                 one-shot default, bounded loop
a unit                   written, NOT enabled
health + routes + verifier + tests + artifacts + docs
```

## What it will not do

The orchestrator wakes the scheduler. It does not make the scheduler able to do
anything it could not do before:

```text
approved sources          0, unchanged
collectors                none exist; Gate 161
terms                     171 blocked, on a human
jobs_completed            0, and the database still refuses one
source_monitoring_live    false
last_checked_at           not advanced by this gate
```

A trigger that fires is not a source that was checked. A running timer is not
live monitoring.
