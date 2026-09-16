# 820 — Gate 157: worker health

```text
worker_runtime_ready     true
source_monitoring_live   false
```

## Six conditions, each established by something that ran

```text
cycle_completed          a cycle ran and its own invariants were clean
claim_is_atomic          a second worker's claim on a held job was refused
expired_lease_reclaimed  a lease past its expiry was taken by another worker
retries_are_bounded      a retry at the attempt budget returned should_retry false
only_transient_retries   no activation, terms or human-review refusal retried
no_collector_invoked     zero, and no path reaches one
```

Not "the modules import". Gate 98E already detects importability, and an import
proves a file parses.

## Zero completed jobs is the expected answer

No handler exists, so nothing can complete. `jobs_completed: 0` is what a
correct worker reports, and an invariant fails if it is ever anything else:

```text
jobs_completed > 0                        ->  refused
jobs_retryable > 0 with an empty allowlist ->  refused
a non-transient class marked retryable     ->  refused
source_monitoring_live true                ->  refused
```

The second one matters most. A retryable job while nothing is approved would
mean a refusal had been misclassified as a hiccup — the single defect this
gate's retry policy exists to prevent.

## What the health report will not guess

```text
worker_process_active   null
```

`null` means nobody measured it, not `false`. The worker runs one cycle and
exits; no unit is installed or enabled, and a request cannot know whether a
process is running without shelling out — which Gate 154 established a route
must never do.

The route's health response says which conditions it did **not** measure, and
points at the verifier that does:

```text
measured_by_the_verifier
  cycle_completed  claim_is_atomic  expired_lease_reclaimed  retries_are_bounded
```

A request does not claim leases, so the conditions that need a real claim are
measured where a real claim happens.

## Stale leases are reported, not swept

A lease past its expiry with an owner still on it means a worker died holding a
claim. It is counted and reclaimable by the next worker. Nothing sweeps them on
a timer, because a sweeper is a scheduled job and Gate 159 owns triggers.

## Reading the lane honestly

```text
a worker exists                        yes
it claims jobs safely                  yes, atomically, with expiry
it recovers from a restart             yes, the lease table is the state
it retries genuine failures            yes, bounded, deterministic
it retries human blockers              no, and an invariant enforces that
anything was collected                 no
anything was permitted to run          no, 0 of 177
source_monitoring_live                 false
background_worker_available            false, deliberately
```

A worker that claims 177 jobs and is refused by all 177 is a worker that works,
attached to a system that collects nothing. The difference from having no worker
is that this one can say, per source, exactly who has to do something before it
could.
