# 822 — Gate 158: what owns pending work, and why nothing does

Read-only survey. Every value was measured by running the code it describes.

## Job identity is already deterministic

Gate 99B has it, and Gate 158 must not write a second one:

```python
build_job_id(source_id, collector_id, job_type, scheduled_for, execution_mode)
build_idempotency_key(source_id, collector_id, job_type, scheduled_for)
```

Measured:

```text
same source + same slot, twice     -> same id          True
same source, different slot        -> different id     True
idempotency key is mode-independent                    True
scheduled_for = None               -> one perpetual slot
```

Both are sha256 over stable inputs. Neither reads a PID, a worker id, a random
UUID or a wall clock. **158D's requirement is already satisfied**, so the Gate
158 identity service composes these rather than replacing them — the same
discipline Gate 156 applied to the job model and Gate 157 to the worker.

That last row matters for bounding the store: a source with no cadence has a
single perpetual slot, so it yields **one** job row forever rather than one per
scheduler cycle.

## The gap, measured

```text
scheduler cycle produced          1 job (in memory)
rows written anywhere             0
=> scheduler output persisted     False
```

**Nothing exists until a worker looks at it.** A scheduler cycle that runs and
then the process dies leaves no trace. Queued work is not durable; only
*claimed* work is, and only because the worker wrote a lease row on its way
past.

## The lease table has become a de facto job store

`nf_source_collection_job_leases` (Gate 157, migration 0043) carries:

```text
a claim            lease_owner  lease_acquired_at  lease_expires_at
a lifecycle        lease_status: pending|claimed|completed|refused|
                                 retryable|failed|expired|unknown
retry accounting   attempt_count  max_attempts  next_retry_at
a refusal reason   failure_class  blocked_reasons
```

The first row is a lease. **The other three are job facts living on a lease
row.** Gate 157 put them there because the worker had nowhere else to write, and
it was the right call for one gate: a lease without an attempt count cannot
bound a retry across a crash.

It is the wrong shape to keep. A lease answers *who holds this right now*; a job
answers *does this work still need doing*. They have different lifetimes — a
lease expires in five minutes, a job survives until it is done or archived — and
one row cannot have two lifetimes.

## The table this gate must not use

`nf_source_check_runs`, whose `check_status` vocabulary is:

```text
scheduled  running  succeeded  succeeded_with_warnings  failed  canceled
```

beside `opportunities_seen_count`, `new_candidates_count` and `accepted_count`.
That is the record of a check that **happened**. Gate 157 already declined it
for leases, for the same reason it must be declined here: a queue row written
there asserts a source was contacted when none was.

## What else could own pending work

Measured across all 41 tables, anything with a `status` column or a job-ish
name:

```text
nf_grant_pursuits      a tenant's pursuit of a grant. Not collection work.
nf_operator_actions    an operator did something. Evidence, not a queue.
nf_pursuit_briefs      generated output.
nf_pursuit_tasks       human tasks with a due_at. Not machine work.
nf_source_collection_job_leases   the lease, discussed above.
```

None owns pending collection work, and none should be bent into doing so.

## Can a job lifecycle be reconstructed today?

Partly, and only for work a worker already touched:

```text
was this job created?        unknowable - creation is not recorded
was it queued?               unknowable - there is no queued state
was it claimed?              yes, if a lease row exists
was it refused, and why?     yes, failure_class + blocked_reasons
was it retried?              attempt_count, if the lease row survived
was it canceled?             no vocabulary for it
was it completed?            the word exists in the enum. Nothing sets it,
                             and nothing should until a collector runs.
```

So the lifecycle is reconstructible from the middle onwards. The beginning — the
part that tells you work is *waiting* — does not exist.

## The exact persistence gap

```text
missing   a durable row that means "this collection job needs doing",
          created by the SCHEDULER, surviving a restart, and idempotent
          across repeated cycles
missing   a lifecycle vocabulary that includes queued and canceled
missing   an authoritative owner for attempt_count and next_retry_at that
          is not also a five-minute claim
missing   a refused record that outlives the worker pass that produced it
```

## The 158E decision: durable refused job rows, not scheduler findings

Two models were available. This gate picks **A: blocked sources get durable job
rows.**

```text
A  every evaluated source gets a job row, including refused ones
B  blocked sources stay scheduler findings, with no queue row
```

**Why A.** The campaign's headline human blocker is 171 terms-blocked sources.
A refusal that exists only inside one worker pass is a backlog nobody can
measure over time — and "how long has this been waiting" is the question that
eventually makes someone read the terms. Option B would keep the store tidy and
leave the backlog invisible, which is the trade this campaign has consistently
refused.

**Why it is bounded rather than unbounded.** The prompt's warning is real: a
naive implementation creates 177 new refused rows every cycle. It does not,
because the job id is deterministic over `(source_id, slot)` and the table has a
unique index on it. Measured above: a source with no cadence has **one**
perpetual slot. So repeated cycles re-enqueue the same ids and the store stays
at one row per source per slot — 177 rows, not 177 per cycle.

A source that *does* have a cadence gets a new row per slot, which is correct:
last week's missed window and this week's pending one are different work.

## The boundary this gate must draw and keep

```text
nf_source_collection_jobs     authoritative for the LIFECYCLE
  status, attempt_count, next_retry_at, terminal_reason, archived_at

nf_source_collection_job_leases  authoritative for the CLAIM
  lease_owner, lease_acquired_at, lease_expires_at
```

The job row is what survives; the lease row is what expires. The worker writes
both — a lease to take the claim, a job transition to record the outcome — and
the job store never stores an owner or an expiry, because Gate 157 already owns
those and two places is how they come to disagree.

## What Gate 158 builds

```text
migration 0044   nf_source_collection_jobs, lifecycle only
a repository     enqueue (idempotent), read, transition, archive, count
an identity svc  composing Gate 99B's digest, not replacing it
scheduler comp   a cycle can enqueue; repeated cycles do not duplicate
worker comp      claims from the store, records transitions on the job row
health           collection_job_store_ready, and jobs_completed = 0
```

## What it will not do

`completed` exists in the vocabulary and **nothing in this gate can set it**. A
transition to `completed` requires an execution proof that no gate has yet
defined, and the repository refuses the transition without one. A persisted job
is not proof a collection occurred; a claimed job is not proof a source was
contacted.

`source_monitoring_live` stays false.
