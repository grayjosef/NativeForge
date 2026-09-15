# 812 — Gate 156: what a scheduler needs that this repository does not have

Read-only survey. Every value below was measured by running the service that
owns it.

## Five gates already built scheduler *pieces*

```text
98B  source_schedule_decision_service      evaluate_schedule()      CONTRACT
98C  source_circuit_breaker_service        evaluate_circuit()       CONTRACT
98D  source_check_run_contract_service                              CONTRACT
98E  source_scheduler_readiness_service    build_scheduler_readiness()  DETECTOR
99B  source_scheduler_job_model_service    build_source_job()       EXECUTABLE
99C  source_scheduler_queue_service        build_dry_run_queue()    EXECUTABLE
100B source_worker_runtime_decision_service                         DECISION
100C source_scheduler_dry_run_worker_service run_dry_run_worker()   EXECUTABLE
143  source_monitoring_readiness_service                            DETECTOR
```

A job model, a queue and a dry-run worker all exist and all run. **Gate 156 must
not build a second job model** — `source_collection_job_model_service` would sit
one word away from `source_scheduler_job_model_service`, which is how Gate 153
overwrote a 320-line module by accident.

## The two things called `scheduler_runtime`, and why that is not a defect

Measured:

```text
detect_scheduler_runtime().available        False   packages_found: []
components["scheduler_runtime"].available   False   -> components_missing
scheduler_runtime_available                 True
runtime_mode                                dry_run_in_process
scheduler_package_installed                 False
```

`scheduler_runtime_available: True` and `components_missing: [scheduler_runtime]`
are both correct and describe different things. Gate 99D found this and fixed it
deliberately:

> `scheduler_runtime_available` used to mean "a scheduler package is installed".
> A bare boolean would have to lie in one direction or the other, so the boolean
> is derived from the mode and always reported beside it.

The narrow question kept its own field, `scheduler_package_installed`. Both are
reported together. This is careful prior work, not a bug, and this gate says so
rather than claiming a finding it does not have.

## But it does change what Gate 156 should build

Gate 143 turns `components_missing` into activation blockers, and Gate 155
counted them:

```text
scheduler_component_absent:scheduler_runtime              <- means NO PACKAGE
scheduler_component_absent:background_worker
scheduler_component_absent:periodic_trigger
scheduler_component_absent:persistent_backend
scheduler_component_absent:production_raw_payload_store
```

`components["scheduler_runtime"]` is `find_spec` over eight third-party
packages: apscheduler, dramatiq, arq, huey, schedule, croniter, taskiq,
procrastinate. None is installed.

So the blocker literally reads **"no scheduler package is installed"** — and
`pip install apscheduler` would clear it while building nothing, touch
`uv.lock`, and add a dependency this system does not need.

**The blocker names a package. The missing capability is something else.**

## What is actually missing

Measured against every existing service:

```text
1. nothing computes a next run time
   `evaluate_schedule` takes `next_check_due_at` as an INPUT and compares it to
   a supplied `now`. No code turns an interval plus a last-checked timestamp
   into the next one.

2. nothing runs a cycle
   the queue builds a list, the dry-run worker marks jobs. Neither walks the
   registry against a clock and reports what is due.

3. nothing reports scheduler health as a lane
   readiness is detected; there is no machine-readable "the scheduler ran a
   cycle and here is what it found".
```

Those three are what a scheduler runtime *is*. A package would provide a timing
loop; it would not provide any of them, because all three are about this
system's sources.

## Persistent scheduler state already exists

`nf_opportunity_sources` carries every field a scheduler needs:

```text
check_interval_days          the cadence
next_check_due_at            the computed due time
last_checked_at              when it last ran
last_successful_check_at
last_check_status
last_check_run_id
consecutive_failure_count
consecutive_empty_check_count
source_health_status
is_active
```

**No migration is needed.** Gate 156D permits this explicitly — document why and
prove deterministic reconstruction instead. Alembic head stays at 0042.

Adding `nf_source_collection_scheduler_jobs` would duplicate ten columns that
already exist and create two places to ask when a source is due, which is how
they come to disagree.

## Can anything currently call a source?

```text
collectors registered            0
activation_approved sources      0
registry rows                  177
terms_blocked                  171
human_review_blocked             6
```

`verify_nativeforge_no_live_source_calls.sh` passes: a chokepoint scan proves no
code path reaches a live source. The dry-run worker reports
`collectors_executed: false`, `urls_fetched: false` on every run, derived rather
than asserted.

With **zero** sources approved, a scheduler has no URL to fetch even if it
wanted one. That is what makes this gate safe to build now rather than after the
terms review: the empty allowlist is not a flag to be respected, it is an
absence of anything to call.

## No scheduling library, and none will be added

```text
apscheduler dramatiq arq huey schedule croniter taskiq procrastinate
```

None installed, none in `pyproject.toml`. Gate 156 adds none: `uv.lock` stays
untouched, and a scheduler that computes next-run times from an injectable clock
needs nothing beyond the standard library.

The consequence is honest and worth stating: **`scheduler_package_installed`
stays false after this gate**, so Gate 143 will keep listing
`scheduler_component_absent:scheduler_runtime`. Gate 156 does not clear that
blocker as written. It builds the capability the blocker was standing in for,
and says plainly that the two are not the same.

## No periodic trigger either

```text
ops/systemd/    nativeforge-cloudflared.service
                nativeforge-demo-preview.service
                nativeforge-mayhem-tunnel.service
```

No `.timer`, no `.cron`. Gate 159 is the planned gate for that; Gate 156 builds
a cycle that something can call, not the thing that calls it.

## What Gate 156 builds

```text
a runtime      computes next_run_at from an interval and a clock, evaluates
               every registry source, and reports state per job
a loop         one deterministic cycle, injectable clock, no thread required
a health lane  scheduler_runtime_ready, jobs known/due/executable/blocked
routes         GET health, jobs, blockers; POST a dry-run evaluation
```

It reuses Gate 99B's job model rather than writing a second one, calls no
collector, opens no socket, and cannot make `source_monitoring_live` true.

**Expected executable jobs after this gate: 0.**
