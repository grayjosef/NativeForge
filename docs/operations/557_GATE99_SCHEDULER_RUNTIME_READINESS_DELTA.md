# 557 — Gate 99D/F: scheduler runtime readiness delta

`src/nativeforge/services/source_scheduler_readiness_service.py`

## What changed

Gate 98 reported:

```text
scheduler_runtime_available   false
background_worker_available   false
source_monitoring_live        false
ready_to_start_monitoring     false
```

Gate 99 reports:

```text
runtime_mode                  dry_run_in_process
scheduler_runtime_available   true      <- changed
background_worker_available   false
source_monitoring_live        false
ready_to_start_monitoring     false
```

One value moved. The three that matter for safety did not.

## Why a mode, and not just a boolean

Gate 98's `false` meant "no scheduler package is installed". Gate 99 built an
in-process queue builder, so the honest answer became neither plain yes nor plain
no — and a bare boolean would have to mislead in one direction or the other.
Leaving it false would deny something that now exists; setting it true without
qualification would be read as a production scheduler.

So `runtime_mode` carries the real answer and the boolean is derived from it:

```text
none                        nothing at all
dry_run_in_process          a queue can be built here, executing nothing
external_worker_configured  a worker exists but is not proven live
production_worker_live      a worker is running and consuming jobs
```

Each rung is resolved from the strongest evidence downward, so a stronger mode
is never reported on weaker evidence. A test walks all four rungs by controlling
the worker, trigger and dry-run detections independently.

`scheduler_package_installed` remains available separately, still answering the
narrow question Gate 98 was asking, and still `false`.

## The mode travels with the boolean everywhere

`runtime_mode` was added to the Gate 98 artifact declarations, so every readiness
artifact — and every row of the components CSV — now carries it beside
`scheduler_runtime_available`. A row reading `True` on its own, copied into a
spreadsheet or a status page, would be taken for a production scheduler. The mode
is the only thing that says otherwise, so it is never separated from it.

## What a dry-run runtime may not do

`source_monitoring_live` is derived from `runtime_mode in LIVE_RUNTIME_MODES`,
not from `scheduler_runtime_available`. A dry-run runtime cannot contribute to a
claim that monitoring is live however many other components appear beside it, and
an invariant fails any result where it does.

That guard is currently belt-and-braces: the mode is derived from the worker and
the trigger, so a dry-run mode alongside both of them cannot arise naturally. A
mutation loosening it survived every other test — noted rather than papered over,
and there is now a test that forces the inconsistent state directly, so a future
change to the mode ladder that makes it reachable fails there rather than
starting monitoring.

## Gate 98F is unaffected, deliberately

`source_activation_preflight_service` and
`phase1_collector_activation_policy_service` both ask
`scheduler_runtime_available and background_worker_available`. The worker half is
still false, so:

```text
preflight  _scheduler_runtime_available()   false
policy     _scheduler_runtime_available()   false
policy     _monitoring_live()               false
sources_may_schedule_monitor                0
monitors_active                             0
```

A dry-run runtime makes no source schedulable. That is checked in Gate 99's own
tests and listed in the selection guard's critical set, because it is the
property most likely to break quietly when a worker is eventually added.

## 99F artifacts

`artifacts/source_scheduler_dry_run/`

```text
source_scheduler_dry_run_queue.json
source_scheduler_dry_run_queue.csv
source_scheduler_runtime_readiness.json
source_scheduler_dry_run_summary.md
```

Every file states seven declarations, and the CSV stamps them on every row
alongside `runtime_mode`:

```text
dry_run_only            true
live_jobs_created       0
collectors_executed     false
live_fetch_performed    false
raw_payloads_written    false
source_monitoring_live  false
live_source_coverage    false
```

Built from the five real Phase 1 sources with the state they actually have — not
a fixture and not a happy path. Every one is blocked, with the reason attached.
An artifact showing an invented set of green sources would be worse than no
artifact, because somebody would read it as a forecast.

Generation uses a fixed reference clock, so the committed files match a fresh
generation; that comparison is the check that makes committing them worthwhile.
The writer computes claim failures first and refuses to write rather than emit a
file whose declarations disagree with the queue behind them — verified both by
forcing a live job into the bundle and by forging a declaration, each of which
leaves the directory absent.

## What remains before monitoring can start

### Engineering

```text
- a background worker        a process that consumes queued jobs
- a periodic trigger         a timer, cron entry, or platform scheduler
- an object store deployment Gate 97's seam, configured and round-tripped
```

The first two are one decision — *where does the worker run* — rather than two.
Gate 99A confirmed no dependency is needed for the dry-run queue and `uv.lock`
did not change; the dependency question returns with the worker, and it is a
deployment choice (which broker, which host) rather than something to pre-empt.

### Unchanged human decisions

```text
- SAM.gov API key and role                    10/day without it
- 185 terms-queue items reviewed              148 + 62 + 4 + 1
- four SPA terms pages read by a human
- Simpler.Grants.gov tribal applicant_type enum
```

None of these is engineering, and none moved in this gate.

## Production boundary

```text
controlled customer pilot     NO_GO
production rollout            NO_GO
scheduler runtime             DRY RUN ONLY (dry_run_in_process)
background worker             NOT AVAILABLE
source monitoring live        0
collectors live               0
crawler live                  0
source coverage live          0
raw payload store production  NOT AVAILABLE
```
