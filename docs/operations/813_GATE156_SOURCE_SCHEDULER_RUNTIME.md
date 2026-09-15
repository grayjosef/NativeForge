# 813 — Gate 156: the source scheduler runtime

```text
scheduler_runtime_ready    true
source_monitoring_live     false
jobs known                 177
jobs executable            0
collectors invoked         0
live source calls          0
```

## What was actually missing

Gates 98–100 built a schedule *decision*, a job model, a queue and a dry-run
worker. All four exist and all four run. None of them does any of this:

```text
1  compute a next run time     `evaluate_schedule` takes `next_check_due_at`
                               as an argument. Nothing produced one.
2  run a cycle                 the queue builds a list; the dry-run worker
                               marks jobs. Neither walks sources against a
                               clock and reports what is due.
3  report scheduler health     readiness was detected by import. An import
                               proves a file parses, not that it evaluates.
```

Gate 156 builds those three.

## The blocker this gate deliberately does not clear

Gate 143 reports `scheduler_component_absent:scheduler_runtime`. Measured, that
is `find_spec` over eight third-party packages:

```text
apscheduler  dramatiq  arq  huey  schedule  croniter  taskiq  procrastinate
```

None is installed. **`pip install apscheduler` would clear that blocker without
computing a single due date.** A package provides a timing loop; it cannot know
when a NativeForge source is due, because that depends on a cadence and a last
check that live in this system.

So no package was added, `uv.lock` is untouched, `scheduler_package_installed`
is still false, and Gate 143 will keep listing the blocker. The capability and
the package are different things, and this gate built the capability.

## Two things share the name `scheduler_runtime`, and that is not a defect

```text
scheduler_runtime_available      True    a runtime MODE exists (dry_run_in_process)
scheduler_package_installed      False   no third-party package
components[scheduler_runtime]    False   the same narrow question, feeding
                                         components_missing
```

Gate 99D found this and split the field on purpose, reporting both side by side:

> A bare boolean would have to lie in one direction or the other, so the boolean
> is derived from the mode and always reported beside it.

This gate records it because it explains the blocker, not because it is a
finding.

## No migration was added

`nf_opportunity_sources` already carries every field a scheduler needs:

```text
check_interval_days   next_check_due_at   last_checked_at
last_check_status     last_check_run_id   consecutive_failure_count
source_health_status  is_active
```

A new `nf_source_collection_scheduler_jobs` table would duplicate ten columns
and create two places to ask when a source is due, which is how they come to
disagree. **Alembic head stays at 0042.**

## Six states, and `due` is not `executable`

```text
scheduled   a cadence is known, the next run is in the future
due         the clock has come round
waiting     no cadence, or no clock; nobody has decided when
blocked     something says no, and it is named
disabled    the source is switched off
unknown     the inputs do not describe a state
```

A job can be `due` and still refuse. `due` is a fact about a clock; `executable`
is a fact about approvals. The evaluation reports both, because "it is overdue
**and** it is blocked" is the useful answer — hiding the first behind the second
makes a backlog invisible.

## `executable` requires every prerequisite affirmatively true

Not "no blockers found", which reads absence of evidence as permission:

```text
activation_state     must equal  activation_approved
terms_state          must equal  terms_approved
human_review_state   must equal  human_review_cleared
collector_registered must be     true
the clock            must have   come round
```

A source whose terms nobody has read is `UNKNOWN`, and `UNKNOWN` blocks. All 177
registry rows are in exactly that position today.

## The clock is an argument

There is no `datetime.now()` in the runtime or the loop, and a test parses both
modules' ASTs to prove it. The same sources and the same instant give the same
counts, which is what lets a verifier assert an exact number instead of a range.

## It is a cycle, not a daemon

`run_scheduler_cycle` evaluates once and returns counts. It starts no thread,
sleeps for nothing and holds no loop. Something else decides when to call it,
and in Gate 156 that something is a test, a verifier or a route.

It is deliberately **not** attached to the FastAPI lifespan hook Gate 102 added:

```text
a request-scoped scheduler runs only while a request is in flight, which is
not a schedule

a scheduler attached to the web process makes "restart the API" and "skip a
collection window" the same action
```

A process is Gate 157's question and a trigger is Gate 159's.

## No systemd unit was created

156G permits one "if architecture supports a separate user service safely". It
does not yet: there is no worker process for a unit to run, and a unit that
starts a cycle with nothing to execute would be a process whose only output is a
log line. Gate 157 builds the worker; the unit belongs with it.

## Routes

```text
GET  /v1/nf/demo/orgs/{org}/source-scheduler/health
GET  /v1/nf/demo/orgs/{org}/source-scheduler/jobs
GET  /v1/nf/demo/orgs/{org}/source-scheduler/blockers
POST /v1/nf/demo/orgs/{org}/source-scheduler/dry-run
```

Authenticated demo organization only. The POST computes a cycle against a
supplied clock and returns counts — it dispatches nothing, approves nothing and
writes nothing. A route that could start collection would be a collection
trigger reachable with a session cookie.
