# 819 — Gate 157: leases and retries

## Why a new table, when Gate 156 needed none

Gate 156 reused `nf_opportunity_sources` because it already carried
`check_interval_days`, `next_check_due_at` and `last_checked_at`. There is no
equivalent for a lease.

Four existing tables carry job-ish names. The closest — and the one most likely
to be misused — is `nf_source_check_runs`, whose `check_status` vocabulary is:

```text
scheduled  running  succeeded  succeeded_with_warnings  failed  canceled
```

That is the lifecycle of a check that is happening or has happened, sitting
beside `opportunities_seen_count` and `accepted_count`. **Writing a lease row
there would assert that a check ran when nothing did** — fabricating evidence in
a table other gates read.

So migration **0043** adds `nf_source_collection_job_leases`. Alembic head moves
0042 → 0043.

## What the table cannot hold

```text
no response body     no url            no status code
no credential        no api key        no provider subject
no customer data     no address        no payload of any kind
```

A column that does not exist cannot be filled by a later mistake — the rule that
produced 0041's missing address column and 0042's missing rendered body, applied
here to the thing a collection worker would most plausibly want to stash.

Three columns exist **to be checked**, and the database refuses to set any of
them true:

```text
ck_nf_source_collection_job_leases_no_collector   collector_invoked = false
ck_nf_source_collection_job_leases_no_fetch       url_fetched = false
ck_nf_source_collection_job_leases_no_payload     raw_payload_written = false
```

A test proves it by attempting the UPDATE and asserting an `IntegrityError`.

## Atomicity is the database's job

A unique index on `(organization_id, job_id)` is what makes a duplicate claim
*refusable* rather than merely discouraged. Two workers racing both insert; one
wins, the other receives an `IntegrityError`, and the lease service turns that
into a refusal rather than an exception.

A SELECT-then-INSERT would leave a window between the two statements, and the
window is where the race lives.

## Expiry is the only release that does not need its owner

```text
a live lease      cannot be stolen - not by another worker, and not by a
                  second process sharing the same worker id
an expired lease  can be reclaimed by anybody
a released lease  is released by its owner, deliberately
```

A worker that dies holding a claim would block that job forever without expiry.
A worker that could steal a live claim would make the lease decorative.

Expiry is derived at read time by comparing to a supplied clock. Storing
`expired` would need something to run and write it, and nothing runs.

## A claim is not an attempt

`attempt_count` moves only when something was actually attempted. A refusal
costs no attempt — otherwise a job nobody can run would exhaust its budget and
then look permanently failed, which is a different and much worse-looking
problem than "a human needs to read some terms".

## Only one failure class retries

```text
refused_by_activation      NOT a retry
terms_blocked              NOT a retry
human_review_blocked       NOT a retry
permanent_worker_failure   NOT a retry
unknown                    NOT a retry
transient_worker_failure   the ONLY class that retries
```

An activation refusal is not a hiccup. No approval exists, and none appears
because a worker tried again in five minutes. Retrying it would produce a worker
that looks busy, burns its budget on jobs that can never run, and never surfaces
that 171 sources are waiting on a person.

**With zero approved sources, all 177 jobs land in a non-retrying class.** A
retry queue filling up here would be the clearest possible sign the
classification was wrong.

`unknown` is deliberately in the non-retrying list: assuming an unclassified
failure is transient would make UNKNOWN a retry loop.

## Blockers are matched by exact value

```text
source_terms_not_approved       -> terms_blocked
source_activation_not_approved  -> refused_by_activation
```

Those two differ by one word. A substring match over either would catch the
other, which is this campaign's most frequent defect and one Gate 157 committed
again in its own verifier's cleanup — see doc 821.

When a job carries both, **terms wins**: the terms review is the thing a person
does first, and naming the later blocker would send them to the wrong queue.

## Bounded, in the database

```text
attempt 1 -> 60s    attempt 2 -> 120s    attempt 3 -> 240s    cap 3600s
```

Deterministic, exponential from a base, capped, and **no jitter**: jitter buys
herd-avoidance among many workers, there is one worker, and a reproducible
next-retry time is worth more than a theoretical thundering herd this system
cannot have.

`max_attempts` lives on the lease row, not in memory. A worker holding its
budget in memory would reset it on every crash — precisely when a bound matters
most. A CHECK constraint enforces `attempt_count <= max_attempts`, so a budget
that can be exceeded is not a budget.
