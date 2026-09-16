# 826 — Gate 158 delta: what changed, and what is next

## Lanes

```text
collection_job_store_ready    created, and TRUE
worker_runtime_ready          unchanged, true
scheduler_runtime_ready       unchanged, true
source_monitoring_live        unchanged, FALSE
approved_source_count         unchanged, 0
```

One lane was created. None that was false became true.

## What Gate 158 added

```text
migration 0044          nf_source_collection_jobs, lifecycle only
a repository            enqueue (idempotent), read, list, transition,
                        archive, count_backlog, capability
an identity service     composing Gate 99B, not replacing it
a scheduler mode        evaluate_and_enqueue, opt-in
a worker capability     records outcomes on the durable row, and can load
                        the durable backlog
a health lane           collection_job_store_ready, 7 conditions
5 routes                4 GET, 1 dry-run POST that writes and rolls back
a verifier              33 checks, restart proven in separate processes
112 tests
9 artifacts
4 docs                  823, 824, 825, 826
```

## What it did not add

```text
a collector                     Gate 161
a periodic trigger              Gate 159
raw payload persistence         Gate 160
an approved source              Gate 162, and then a human
accepted source terms           a human. No gate clears this.
an execution proof              undefined. See below.
a completed job                 refused by the database
```

## The one deliberate hole

`execution_proof_ref` exists as a column and is null on every row. Nothing
writes it, and `transition_job` has no parameter that could.

That is not an oversight to tidy up later. Defining what an execution proof *is*
is the moment "a job finished" becomes a claim this system can make, and it
should cost a gate of its own rather than arriving as a convenience inside one
about persistence. Until then `completed` is a word in a vocabulary that the
database refuses to write.

Leaving the word out entirely would have been worse: a job lifecycle with no
terminal success state is incomplete, and it would have been added later under
pressure, by whoever needed it that day.

## What still blocks a collection, in order

```text
1  a periodic trigger        Gate 159. Nothing fires on its own; a cycle runs
                             when a person or a script runs it.
2  raw payload persistence   Gate 160. There is nowhere to put a response.
3  a collector envelope      Gate 161. No code can fetch anything.
4  source allowlist boundary Gate 162. Zero sources are approved, and this is
                             where approval gets defined.
5  source terms              a HUMAN must read them. 171 sources.
6  human review              a HUMAN must look at each source.
```

Items 1 to 4 are engineering. Items 5 and 6 are not, and no amount of runtime
makes them so. Gate 155's rule stands: **do not recommend more wrapper gates
around a blocker only a person or an approval can clear.**

## The block's intent, checked

> Build the runtime machinery required for source collection while keeping every
> live-source path hermetic and inactive. Do not let runtime existence imply
> live monitoring.

Four separations the block asked for, and where each one now lives:

```text
runtime exists            collection_job_store_ready = true
collection is approved    approved_source_count = 0
source terms approved     171 blocked, terms_state = terms_unknown
live monitoring active    source_monitoring_live = false
```

All four are separately reportable, and Gate 158 moved only the first.

## Gate 159 carry-forward

```text
- Gate 158's store is where a triggered cycle writes. Do not add a second.
- A trigger that fires is not a source that was checked.
- Do not equate a running timer with live monitoring.
- `evaluate_and_enqueue` needs a connection; a timer must supply one without
  holding it open across a sleep.
- Do not put a lease on a job row, and do not put a lifecycle on a lease row.
  0043 owns the claim, 0044 owns the lifecycle.
- A re-enqueue must stay create-if-absent. A trigger that reset refused rows to
  queued would erase the backlog age this campaign wants to measure.
- `refused -> queued` exists for a CLEARED BLOCKER, not for a new cycle.
- source_monitoring_live remains false.
- Nothing may set execution_proof_ref.
```

## A note on the alembic head pins

Migration 0044 moved **ten** real head pins from 0043. They were found on the
first pass this time, by running the unquoted structural search Gate 151 asked
for and Gate 157 skipped:

```bash
grep -rn "004[0-9]" --include=*.py --include=*.sh src/ scripts/ tests/
grep -rn "(head)" --include=*.py --include=*.sh src/ scripts/ tests/
```

The second command is the one that matters. One pin reads `== "0043 (head)"` and
survives any grep for the bare quoted revision — the trap that caught Gate 151
and then caught Gate 157 one gate after the warning was written into the file.

Eleven mentions of 0043 were deliberately left alone: prose about which
migration created which table, file paths, and Gate 154's synthetic
`migration_ahead` comparator fixtures. One line in Gate 157's verifier was
changed from `alembic_head=0043` to `migration_added_by_this_gate=0043`, because
it was a claim about the head that went stale the moment 0044 landed, when what
it meant was which migration that gate added.
