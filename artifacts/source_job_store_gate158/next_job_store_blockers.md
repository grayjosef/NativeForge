# Next: what still stands between a job store and a collection

Gate 158 made the collection job lifecycle durable. Nothing in it contacted a
source, and nothing in it could.

## What is now true

```text
queued work survives a process restart        proven by a second process
enqueue is idempotent across repeated cycles  5 cycles, 3 rows
a refusal outlives the worker that recorded it
the backlog reason stays countable            terms_blocked, not unknown
a completed job cannot exist                  refused by repository AND database
```

## What still blocks a collection, in the order it has to clear

```text
1  a periodic trigger        Gate 159. Nothing fires on its own yet; a cycle
                             runs when a person or a script runs it.
2  raw payload persistence   Gate 160. There is nowhere to put a response.
3  a collector envelope      Gate 161. No code can fetch anything.
4  source allowlist          Gate 162. Zero sources are approved, and this is
                             the boundary that decides approval means.
5  source terms              a HUMAN must read them. 171 sources are blocked
                             on this and no gate can clear it.
6  human review              a HUMAN must look at each source.
```

Items 1 to 4 are engineering. Items 5 and 6 are not, and no amount of runtime
makes them so. Gate 155's rule stands: do not recommend more wrapper gates
around a blocker only a person can clear.

## What Gate 158 deliberately did not do

`execution_proof_ref` exists as a column and is null on every row. Nothing
writes it, and `transition_job` has no parameter that could. The gate that
defines what an execution proof *is* has not been written, so `completed`
remains a word in a vocabulary rather than a state anything can reach.

Defining it is the moment "a job finished" becomes a claim the system can make,
and it should cost a gate of its own.

## What the durable backlog now makes askable

```text
how many jobs are waiting, by status
how long has the oldest one waited          oldest_live_job_queued_at
why is each one blocked, by terminal reason
```

That last line is the argument for having persisted refused jobs at all. The
count was the point.
