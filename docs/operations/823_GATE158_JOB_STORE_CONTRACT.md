# 823 — Gate 158: the collection job store contract

`nf_source_collection_jobs`, migration 0044. What it holds, what it refuses, and
which of those refusals the database enforces rather than the code.

## The boundary

```text
nf_source_collection_jobs        the LIFECYCLE
  status  attempt_count  next_retry_at  terminal_reason  archived_at

nf_source_collection_job_leases  the CLAIM
  lease_owner  lease_acquired_at  lease_expires_at
```

A lease answers *who holds this right now* and expires in five minutes. A job
answers *does this work still need doing* and survives until archived. They have
different lifetimes, and one row cannot have two.

Gate 157 put attempt accounting on the lease row because the worker had nowhere
else to write it, and that was right for one gate: a lease without an attempt
count cannot bound a retry across a crash. This table is the somewhere else.

**It declares no owner column and no expiry column.** A column that does not
exist cannot drift from the table that owns it, and `job_store_capability()`
derives that claim by reading the declared table rather than asserting it.

## The table Gate 158 declined, again

`nf_source_check_runs.check_status` is
`scheduled|running|succeeded|succeeded_with_warnings|failed|canceled`, beside
`opportunities_seen_count` and `accepted_count`. That is the record of a check
that **happened**. A queue row written there asserts a source was contacted when
none was — the reason Gate 157 declined it for leases and Gate 158 declines it
for jobs.

## The lifecycle

```text
queued      work exists and needs doing
claimed     a worker holds it right now
refused     a worker looked and would not run it, and said why
retry_wait  a transient failure, waiting on a backoff
canceled    an operator stopped it
completed   in the vocabulary. Nothing can reach it. See below.
failed      permanently, and not for a reason a retry fixes
archived    where a job stops
```

The transitions, from `LEGAL_TRANSITIONS`:

```text
queued      -> claimed, canceled, archived
claimed     -> refused, retry_wait, failed, completed, canceled
refused     -> queued, canceled, archived
retry_wait  -> claimed, failed, canceled, archived
canceled    -> archived
completed   -> archived
failed      -> queued, archived
archived    -> nothing
```

Three of those deserve a sentence.

**`queued -> refused` is absent.** An outcome without a claim never happened, so
a worker must pass through `claimed` to record one. The verifier checks this by
attempting it and confirming the row is untouched.

**`refused -> queued` is present**, and it is the transition this campaign is
built around. 171 sources are terms-blocked. When somebody finally reads those
terms, their jobs become runnable work again rather than needing to be recreated
— and the record of how long they waited survives.

**`archived -> nothing`.** Reviving an archived job would rewrite a closed
history.

## Enqueue is idempotent, and the database is what enforces it

`job_id` is Gate 99B's sha256 over
`(source_id, collector_id, job_type, scheduled_for, execution_mode)`.
Deterministic, and `ux_nf_source_collection_jobs_job_id` is unique over
`(organization_id, job_id)`.

So `enqueue_job` **inserts and catches the integrity error**. It does not check
and then insert, because check-then-insert is a race that two scheduler
processes lose together.

Measured, five cycles over three sources:

```text
cycle 1  created=3  deduplicated=0  rows=3
cycle 2  created=0  deduplicated=3  rows=3
cycle 3  created=0  deduplicated=3  rows=3
cycle 4  created=0  deduplicated=3  rows=3
cycle 5  created=0  deduplicated=3  rows=3
```

That is the bound the survey argued for, and it is a property of the id plus the
index rather than a cap somebody chose. A source with no cadence has one
perpetual slot, so 177 registry sources hold the store at 177 rows rather than
adding 177 a cycle.

A source that **does** have a cadence gets a new row per slot, which is correct:
last week's missed window and this week's pending one are different work. The
verifier checks that too — 3 rows become 6 when the clock moves a month.

Enqueue is **create-if-absent and never an update**, so a later cycle cannot
erase an outcome a worker already recorded.

## `completed` cannot be reached, and the database agrees

```sql
CHECK (status <> 'completed' OR execution_proof_ref IS NOT NULL)
```

`execution_proof_ref` is null on every row. Nothing writes it, and
`transition_job` **has no parameter that could** — not a guard, not a constant,
not a check somebody could invert. The argument does not exist.

That is checked three ways:

```text
the repository refuses the transition and names the reason
the DATABASE refuses it, verified with the repository bypassed by a raw UPDATE
job_store_capability() derives the unreachability from the function signature
```

The third matters most: if a future gate adds the parameter, the reported
capability changes by itself instead of going quietly stale.

**A persisted job is not proof a collection occurred.** That sentence is the
CHECK constraint, enforced.

## The other two constraints

```sql
CHECK (status <> 'retry_wait' OR terminal_reason = 'transient_worker_failure')
```

An activation or terms refusal parked in a retry queue would burn attempts on
work no worker can ever run. Only a genuine transient failure waits.

```sql
CHECK ((status = 'archived' AND archived_at IS NOT NULL)
    OR (status <> 'archived' AND archived_at IS NULL))
```

Set if and only if archived. A live row carrying an archive timestamp, or an
archived row without one, are both refused.

Plus `attempt_count >= 0 AND attempt_count <= max_attempts`, because a budget
that can be exceeded is not a budget.

## What it cannot hold

```text
no response body    no url             no status code
no credential       no api key         no token or cookie
no oauth state      no pkce verifier   no provider subject
no customer data    no address         no object bytes
```

The rule that produced 0041's missing address column, 0042's missing rendered
body and 0043's three refused booleans, applied to the thing a collection queue
would most plausibly accumulate: the results.

## Identity is composed, not rebuilt

`source_collection_job_identity_service` calls Gate 99B's `build_job_id` and
`build_idempotency_key`. It contains no `hashlib` import, and the test checks
that — a second sha256 would be a second source of truth for whether two jobs
are the same job.

It normalizes `job_type` and `execution_mode` through Gate 99B's **imported**
vocabularies rather than its own copies. Doc 825 explains why, because the first
version did not and the ids disagreed.
