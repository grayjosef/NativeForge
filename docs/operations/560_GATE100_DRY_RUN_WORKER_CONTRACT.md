# 560 — Gate 100C/E: dry-run worker contract

`src/nativeforge/services/source_scheduler_dry_run_worker_service.py`
`scripts/run_nativeforge_source_scheduler_dry_run_worker.py`

Consumes Gate 99 queue jobs and marks them. No collector is called, no URL is
fetched, no payload is written, and no monitoring is started.

## A dry-run worker is not a worker, and it is not monitoring

It is the shape a worker would have, exercised against jobs that cannot run.
Processing a job here means reading it, checking it is a kind this worker may
touch, and recording an outcome — everything a worker does *around* the work.
The work itself is absent, and after this gate it is still absent.

```text
collectors_executed     false
urls_fetched            false
raw_payloads_written    false
source_monitoring_live  false
```

All four are constants on every result and all four are held by invariants, both
on the roll-up and on each individual row. The module imports no HTTP client, no
collector, and no body store, checked by parsing its AST rather than grepping its
text.

## What it did

Run against Gate 99F's queue over the five real Phase 1 sources:

```text
jobs_seen             5
jobs_processed        5
jobs_completed_dry_run 0
jobs_blocked_dry_run  5
live_jobs_refused     0
jobs_refused          0
```

Every job blocked, every reason carried through unchanged. The queue was already
blocked for four reasons — no activation, no schedule, an unknown circuit, and no
production payload store — and the worker neither cleared nor summarised any of
them away.

## What it refuses, and why refusing is not skipping

```text
live_collection jobs         refused_live
running/completed/failed     refused_invalid_status
unrecognised execution mode  refused_unknown_mode
replay_fixture, manual_review  skipped_not_processable
```

Every refused job stays in the result with its reason. A worker that silently
dropped the live jobs it would not run would report a clean sweep over the jobs
it liked — the shape of every dishonest green dashboard.

The middle case matters more than it looks. `running`, `completed` and `failed`
describe *execution*, and Gate 99B's invariants already reject a job holding one.
A job arriving here with such a status did not come from Gate 99's queue — it came
from somewhere else, or was edited in between. Either way this worker has no
business touching it, because the one thing it can be sure of is that it does not
know what already happened to that job.

`replay_fixture` and `manual_review` are left alone rather than claimed. The
processable set is `dry_run` only, and widening it is a decision rather than an
oversight.

## Two outcomes, and one careful name

```text
completed_dry_run   a queued job. Nothing ran; it would have been eligible.
blocked_dry_run     a blocked job. Its reasons carry through unchanged.
```

`completed_dry_run` does not mean the check completed — it means the *dry run*
completed. A field called `completed` would be read as a check having happened
within a week of somebody putting it on a dashboard, and the distinction is the
entire gate.

## Deterministic

`worker_run_id` is a sha256 over the queue id and the sorted job ids, with no
clock in it. Results are sorted by job id, so the run is order-independent and
the artifacts regenerate byte-identically. An invariant re-derives the id from
the results, so a record edited after the fact fails rather than passes.

## The CLI

`scripts/run_nativeforge_source_scheduler_dry_run_worker.py`, mode 755,
following the `scripts/*.py` convention Gate 100A confirmed.

```text
exit 0   a dry run completed and was reported
exit 2   a live_collection job was encountered anywhere - refused
exit 3   the run failed its own invariants
exit 4   a result claimed a collector ran, a URL was fetched, or a payload written
```

The live check and the side-effect check both run before the invariant pass, so
their specific messages win, and both read the produced results rather than the
requested mode — a request is an intention, and the results are the fact. The
side-effect check inspects **each row** as well as the roll-up, because a roll-up
can be right while a row is wrong.

Seven tests cover it: it exits 0 doing no live work, JSON mode reports no side
effects, exit 2 on a forced live job, exit 4 on each of the three per-row side
effects, no credential markers in its output, and a run to completion in-process
with `socket.connect` and `socket.create_connection` poisoned to raise.

## Gate 100D: the dry-run worker buys nothing elsewhere

`dry_run_worker` is a component in Gate 98E's readiness detection, kept separate
from Gate 99's `dry_run_runtime` because they are different capabilities — one
builds a queue, the other consumes one.

Neither feeds `background_worker_available`, which has its own detection (a
worker module or a console entry point, of which there are none). Three
invariants hold that line:

```text
dry_run_worker_read_as_a_background_worker      readiness
dry_run_worker_permitted_live_work:<source>     phase 1 policy
safe_to_schedule_on_a_dry_run_worker            activation preflight
```

The last one was rewritten during the gate. It first re-queried detection from
inside the invariant, which meant it validated the machine it was running on
rather than the record it was handed — and it disagreed with a Gate 98 test that
simulated a scheduler runtime. `background_worker_available` is now recorded on
the preflight result and the invariant reads that field, which is both correct
and auditable. The Gate 98 test's simulation was completed to set both halves,
since a world where `_scheduler_runtime_available()` is true is a world with a
worker in it.

Result: `may_fetch_live_now`, `may_schedule_monitor`, `monitors_active` and
`collectors_active` are all still zero or false, with `dry_run_worker_available`
reported true beside them.
