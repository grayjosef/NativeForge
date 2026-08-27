# 553 — Gate 98E/F/G: scheduler readiness and remaining work

`src/nativeforge/services/source_scheduler_readiness_service.py`
`src/nativeforge/services/source_scheduler_readiness_artifact_service.py`

## The four facts

```text
scheduler_runtime_available   false
background_worker_available   false
source_monitoring_live        false
ready_to_start_monitoring     false
```

Each is detected, not declared. `build_scheduler_readiness` takes exactly one
parameter — `repo_root` — so no argument can turn a missing component into a
present one.

## Seven components, each detected by looking at the thing

| Component | Kind | Present | Detected by |
| --- | --- | --- | --- |
| `schedule_decision_service` | contract | yes | import + callable check |
| `circuit_breaker_service` | contract | yes | import + callable check |
| `check_run_contract_service` | contract | yes | import + callable check |
| `production_raw_payload_store` | contract | no | Gate 96/97 derivation |
| `scheduler_runtime` | runtime | no | `importlib.util.find_spec` |
| `background_worker` | runtime | no | find_spec + console entry points |
| `periodic_trigger` | runtime | no | repo file scan |

Ten scheduler and queue packages are checked for importability — celery, rq,
apscheduler, dramatiq, arq, huey, schedule, croniter, taskiq, procrastinate —
and none is installed. No worker module or console entry point exists. No
`.timer` or `.cron` file is checked into the repo.

The trigger scan is scoped to the repository on purpose. A timer installed on one
operator's laptop is not a property of this system, and reporting it as one would
make readiness depend on whose machine ran the check.

## Why not just return False

Gate 97 found two Gate 96 guards written as `x is not False`. They asserted a
constant that was correct at the time and would have failed a *correct* system
the moment the thing became possible.

So `scheduler_runtime_available` is a `find_spec` result rather than a literal.
A test proves the detection is live: with the scheduler packages made importable,
the flag flips to True on its own — and readiness still reports False, because
the worker, the trigger and the payload store remain missing.

## Contracts are not a runtime

`decision_layer_available` is **true**. Gate 98 built three services that a
scheduler would consult. Having them is not having a scheduler, in the same way
that Gate 95's payload contract was not a payload store, and the result reports
the two halves separately so neither can be read as the other. An invariant fails
any result where a complete decision layer was read as readiness.

## 98F — activation is not scheduler readiness

Two services conflated them, and both are patched.

**`source_activation_preflight_service`.** `safe_to_schedule` was
`allowed and monitoring_schedulable`. The `scheduler_policy` requirement is
satisfied by a caller passing `scheduler_status="policy_declared"` — a decision
about *cadence*, not a process. So a fully cleared source came back
`safe_to_schedule: True` on a system with no worker and no queue.

It now additionally requires a detected runtime. Scheduling blockers live in
their own `scheduling_blocked_reasons` list rather than in `blocked_reasons`,
because a missing worker is not an activation blocker: the source is not at fault
for the platform having none, and a source may legitimately be activated for
operator-triggered checks with no scheduler in existence. Folding the lists
together would block activation on a platform fact — the opposite of the
separation this gate draws.

The result today:

```text
activation_status          activation_allowed
activation_allowed         true
scheduler_policy_declared  true
scheduler_runtime_available false
safe_to_schedule           false
scheduling_blocked_reasons ['scheduler_runtime_unavailable']
blocked_reasons            []
```

**`phase1_collector_activation_policy_service`.** `may_schedule_monitor` was
hardcoded `False`, and `monitors_active` and `sources_may_schedule_monitor` were
held at zero by invariants asserting they were zero. That is the same
constant-versus-derivation defect, and all three would have gone on reading zero
after somebody deployed a worker.

They are now derivations — `preflight_passed and scheduler_runtime_available`,
and counts summed from the rows — checked by invariants for *agreement* with what
they summarise. They still read zero today, on their own. A test proves it: given
a runtime and passing preflights, `sources_may_schedule_monitor` becomes 5.

## 98G — five artifacts

`artifacts/source_scheduler_readiness/`

```text
scheduler_readiness.json              readiness + every schedule scenario
scheduler_readiness_components.csv    one row per component
circuit_breaker_states.json           every circuit state, worked
source_check_run_contract.json        the contract shape
scheduler_readiness_summary.md        the human version
```

Every file states the four declarations on its own; the CSV stamps them on every
row, because a row is the unit that gets copied out. The writer computes
`artifact_claim_failures` first and raises rather than writing a file whose
declarations disagree with the detection behind them — verified: forcing
`ready_to_start_monitoring` to true refuses the write and leaves the directory
absent. Generation is deterministic against a fixed reference clock, so a real
`now` cannot change the cooldown arithmetic between runs.

## What remains

### Engineering

```text
- a scheduler runtime          a queue or scheduler package, deployed
- a background worker          a process that consumes the decisions
- a periodic trigger           a timer, cron entry, or platform scheduler
- an object store deployment   Gate 97's seam, configured and round-tripped
```

The first three are one decision — *where does the worker run* — rather than
three. That is a deployment question, not a contract one.

### Consolidation, deliberately not done in this gate

The four failure counters in doc 551 remain. Collapsing `source_freshness_service`
and `discovery_source_quality_service` onto this breaker, and giving
`polite_http_fetch_service` a durable counter instead of a per-process dict, is a
refactor across four call sites with its own regression surface. It is worth doing
and it is not worth doing inside a gate whose subject is something else.

### Human decisions, unchanged since Gate 93

```text
- SAM.gov API key and role                    10/day without it
- 185 terms-queue items reviewed              148 + 62 + 4 + 1
- four SPA terms pages read by a human
- Simpler.Grants.gov tribal applicant_type enum
```

None of these is engineering, and none of them moved in this gate.
