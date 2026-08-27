# 554 — Gate 99A: scheduler runtime survey

Verified rather than assumed. One correction to the brief is recorded at the end.

## Scheduler, worker and queue packages: none, in three places

```text
package        pyproject.toml   uv.lock   importable in .venv
celery                      0         0                    no
rq                          0         0                    no
apscheduler                 0         0                    no
dramatiq                    0         0                    no
arq                         0         0                    no
huey                        0         0                    no
taskiq                      0         0                    no
procrastinate               0         0                    no
schedule                    0         0                    no
croniter                    0         0                    no
kombu                       0         0                    no
redis                       0         0                    no
pika                        0         0                    no
```

Three independent checks — the declaration, the lock, and the environment — and
all three agree. Gate 98E already checked the third; this gate checked the other
two, because a package could in principle be declared and not installed, and
that would be a different answer.

## No job or queue table

```text
grep 'class .*Job|__tablename__.*job|__tablename__.*queue'  src/nativeforge/db/models.py
  -> no match
```

Twenty-odd services mention "queue" in prose or in review-item vocabulary;
`source_terms_review_queue_service` is the closest thing, and it is a pure
function that builds a review list from seeds. None of them is a job queue, and
nothing persists a job.

**This means Gate 99 needs no migration.** The job model is a contract over
values, in the same shape as Gates 95–98. A durable job table is a real decision
with a schema and a retention policy behind it, and it belongs to whichever gate
actually deploys a worker.

## Entrypoints

```text
API routers            26 files, 30 include_router calls in main.py
console_scripts        none declared in pyproject.toml
scripts/*.py           10 (5 executable)
scripts/*.sh          137
```

The Python script convention is settled and consistent:

```python
#!/usr/bin/env python3
"""One-line purpose."""
from __future__ import annotations
ROOT = Path(__file__).resolve().parents[1]
_SRC = ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))
```

with `argparse` and mode `755`. Gate 99E follows it exactly rather than inventing
a location.

## Systemd, timers, cron

```text
nativeforge-demo-preview.service    Vite preview on 127.0.0.1:5175   running
nativeforge-mayhem-tunnel.service   Cloudflare tunnel                running

systemctl --user list-timers        no nativeforge timers
crontab -l                          no nativeforge entries
```

Neither unit schedules anything. There is no periodic trigger of any kind, which
is why `periodic_trigger` stays absent in Gate 98E's detection and why
`background_worker_available` cannot become true in this gate.

## Is a dependency needed? No

A dry-run queue is a pure function from schedule decisions to job records. It
sorts, deduplicates by key, and summarises. None of that needs a broker, a
scheduler loop, or a persistence layer:

```text
what a queue library gives you        what Gate 99 needs
-------------------------------------------------------
a broker and transport                no - nothing is dispatched
worker process management             no - nothing runs
retry and backoff policy              no - Gate 98C's breaker already decides
periodic trigger scheduling           no - no trigger in this gate
serialisation of task payloads        no - values stay in process
```

**`uv.lock` will not change in this gate**, and the constraint against modifying
it is met by not needing to.

The dependency question comes back when a real worker is deployed, and it is a
deployment decision — where the worker runs, and what it uses for a broker —
rather than something to pre-empt here. Doc 557 records it as the open choice.

## Where a future scheduler runtime attaches

Gate 98A mapped the eight steps. Gate 99 fills in step 1.5 and nothing after it:

```text
1    decide      source_schedule_decision_service      due, and safe?
1.5  queue       source_scheduler_queue_service        <- Gate 99, dry-run only
2    breaker     source_circuit_breaker_service        circuit closed?
3    guard       live_network_guard_service            may the request go out?
4    fetch       the approved transport                <- nothing reaches here
5    body        s3_raw_payload_body_store_service
6    metadata    production_raw_payload_repository
7    run record  nf_source_check_runs
8    state       finalize_completed_source_check
```

Steps 4 through 8 stay untouched. The queue produces records describing jobs that
*would* run; a dispatcher that hands them to step 3 does not exist, and building
one is what makes monitoring live.

## Runtime mode: what `dry_run_in_process` may honestly mean

Gate 99D adds a `runtime_mode` vocabulary. The distinction that matters:

```text
none                        nothing at all
dry_run_in_process          a queue can be built, in this process, executing nothing
external_worker_configured  a worker is configured but not proven live
production_worker_live      a worker is running and consuming jobs
```

Gate 99 may reach `dry_run_in_process`, because after this gate the repository
genuinely contains something that builds a queue and runs in-process. It may not
reach further, and `background_worker_available`, `source_monitoring_live` and
`ready_to_start_monitoring` all stay false — detected, as in Gate 98E, not
declared.

A dry-run queue is not monitoring. It is a list of work nobody has agreed to do.

## Correction to the brief

The prompt lists `docs/operations/553_GATE98_SCHEDULER_READINESS_DELTA.md` as an
input. No such file exists. Gate 98's readiness document is:

```text
docs/operations/553_GATE98_SCHEDULER_READINESS_AND_REMAINING_WORK.md
```

Surveyed in its place. Nothing else in the brief's input list was missing.
