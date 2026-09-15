# 815 — Gate 156: scheduler health

```text
scheduler_runtime_ready    true
source_monitoring_live     false
```

Those two lines are the whole lane. The first says the machinery to evaluate a
schedule exists and a cycle runs deterministically. The second says something is
polling a source. Nothing is.

## Six conditions, each established by a cycle that ran

```text
runtime_module_evaluates   a next run time was computed from an interval and a
                           last check - the thing Gates 98-100 do not do
cycle_completed            a cycle returned counts and its invariants were clean
every_job_has_a_state      jobs_by_state accounts for every job; a job with no
                           state would mean the evaluator fell through
clock_is_injected          no datetime.now() in the runtime or the loop
no_collector_invoked       collectors_invoked is 0, and no path reaches one
no_live_source_call        live_source_calls is 0
```

Not "the modules import". Gate 98E already detects importability, and an import
proves a file parses, not that it evaluates anything.

## Zero executable jobs is the expected answer

`jobs_executable: 0` is what a correct scheduler reports today, and the lane is
ready anyway. Readiness is about the machinery, not about whether anything is
permitted to run through it.

An invariant makes the converse impossible:

```text
jobs_executable > activation_allowlist_count   ->  refused
jobs_executable > 0 with an empty allowlist    ->  refused
source_monitoring_live ever true               ->  refused
```

If executable jobs ever appeared while nothing was approved, the allowlist gate
would have failed open — and the health report refuses itself rather than
publishing the number.

## What the health report will not guess

```text
scheduler_process_active   null
```

`null` means nobody measured it, not `false`. A scheduler **process** is Gate
157, and a request cannot know whether one is running without shelling out —
which Gate 154 established a route must never do.

## Persistent state

```text
persistent_state_available   true
```

`nf_opportunity_sources` already carries `check_interval_days`,
`next_check_due_at`, `last_checked_at`, `last_check_status` and
`consecutive_failure_count`. No table was added and alembic head is unchanged.

There is a real gap worth naming, and it belongs to Gate 158: **terms state and
schedule state live in different registries.** The 177-row file registry carries
source identity and health but no terms column; the 40-row database table
carries the cadence. Nothing joins them, so a job built from one has to be told
about the other.

## Reading the lane honestly

```text
a scheduler exists                         yes
it evaluates every source                  yes, 177 of them
it can compute when a source is due        yes
anything is permitted to run               no, 0 of 177
anything was polled                        no
source_monitoring_live                     false
scheduler_package_installed                false, deliberately
```

A runtime that refuses everything is exactly as far from monitoring as no
runtime at all. The difference is that this one can say so, per source, with the
reason attached.
