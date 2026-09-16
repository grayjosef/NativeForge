# 824 — Gate 158: how the scheduler, the store and the worker compose

Gate 156 computes cycles. Gate 157 claims work. Gate 158 makes the lifecycle
between them durable. None of the three was replaced.

## The gap, as Gate 158 measured it

```text
scheduler cycle produced          1 job (in memory)
rows written anywhere             0
=> scheduler output persisted     False
```

Nothing existed until a worker looked. A scheduler cycle that ran and then lost
its process left no trace, so "this work is waiting" was not a fact the system
held — only "a worker already refused it" was, and only because Gate 157's
worker wrote a lease on its way past.

## The flow now

```text
1  run_scheduler_cycle(mode="evaluate_and_enqueue", connection=...)
      evaluates every source against the injected clock
      computes each job identity by composing Gate 99B
      enqueues a durable row per evaluated source, INCLUDING refused ones
      reports rows_written, DERIVED from what it actually wrote

2  the process can now die

3  run_worker_cycle(load_jobs_from_store=True)
      reads the queued and retry_wait backlog
      claims each job on Gate 157's lease
      refuses it, and records the refusal on BOTH the lease and the job row
      transitions queued -> claimed -> refused

4  the refusal outlives the worker that produced it
```

Measured end to end, across three separate connections:

```text
phase 1  a scheduler process enqueues 3 rows, then exits
phase 2  a DIFFERENT connection loads 3 rows it did not write
         jobs_claimed=3  jobs_refused=3  jobs_completed=0
         job_rows_transitioned=6   (two steps per job)
phase 3  by_status: {refused: 3}, completed: 0, proofs: 0
phase 4  the scheduler runs again: created=0, deduplicated=3
phase 5  a second worker pass loads 0 - refused rows are not queued
```

Phase 5 is worth pausing on. A worker does not re-chew a backlog nobody has
unblocked, because `refused` is neither `queued` nor `retry_wait`. Clearing the
blocker is what puts the job back in the worker's path, via `refused -> queued`.

## The mode is opt-in, and the default did not change

```text
evaluate_only          the default, through Gate 157 and still
evaluate_and_enqueue   added by Gate 158, needs a connection and an org
```

Nothing that called `run_scheduler_cycle` before Gate 158 writes a row now. An
enqueue requested without a connection is refused with
`enqueue_requested_without_a_connection` rather than silently evaluating.

## `rows_written` stopped being a constant

Through Gate 157 the cycle reported `"rows_written": 0`, and
`cycle_invariant_failures` refused any nonzero value. That was true only because
the cycle could not write, which is the declared-vs-derived shape this campaign
exists to remove.

It is now counted. And the check was **replaced rather than dropped**:

```text
before   rows_written must be 0
after    rows_written must AGREE with jobs_enqueued
         jobs_enqueued must AGREE with the per-job results
         jobs_deduplicated must AGREE with the per-job results
         an evaluate_only cycle must still have written nothing
         created must never exceed the number of jobs evaluated
```

Deleting the old check would have left a counter nothing verified. A test
tampers with `rows_written` and confirms the checker catches it.

Meanwhile these stayed constants, and stayed in the must-be-zero list:

```text
collectors_invoked  live_source_calls  network_calls
urls_fetched        raw_payloads_written
```

**Persisting is not executing.** A cycle that writes a row still contacted
nothing.

## A store-loaded job is never permitted

Gate 157's rule is that the worker reads the scheduler's `executable` rather
than recomputing it. A store row does not carry `executable`. It carries
`blocked_reasons`, which is a record of *why*, not a grant.

Treating an empty `blocked_reasons` as permission would be inferring source
approval from the absence of a recorded objection. So:

```text
executable   hardcoded False for a store-loaded job
blockers     the persisted reasons, PLUS
             executable_is_not_a_persisted_fact_in_gate_158
```

The permitted branch stays reachable for a job a scheduler pass hands over
directly, so the refusal is falsifiable rather than unconditional. Deciding what
permission means, and where it is persisted, is Gate 162.

## The worker writes both tables, and unions the reasons

```text
a lease        to take the claim, for five minutes
a job row      to record the outcome, for as long as it takes
```

The transition unions the reasons it is recording with the ones the row already
held. Doc 825 explains why that sentence exists.

## What the durable backlog makes askable

```text
how many jobs are waiting, by status         by_status
how long has the oldest one waited           oldest_live_job_queued_at
why is each one blocked                      by_terminal_reason
```

That last line is the whole argument for having persisted refused jobs rather
than leaving blocked sources as scheduler findings. The count was the point.
