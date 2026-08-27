# 561 — Gate 100D/F: production readiness delta

## What changed

Gate 99 reported:

```text
runtime_mode                  dry_run_in_process
scheduler_runtime_available   true
background_worker_available   false
source_monitoring_live        false
ready_to_start_monitoring     false
```

Gate 100 reports:

```text
runtime_mode                  dry_run_in_process
scheduler_runtime_available   true
dry_run_worker_available      true      <- new
external_worker_required      true      <- new
background_worker_available   false
production_worker_live        false
source_monitoring_live        false
ready_to_start_monitoring     false
```

Two facts were added. Nothing that was false became true.

## The dry-run worker is a separate component

`dry_run_worker` joins Gate 98E's component set, kept distinct from Gate 99's
`dry_run_runtime`: one builds a queue, the other consumes one, and a system could
plausibly have either without the other.

```text
component                     kind      present  detected by
schedule_decision_service     contract  yes      import + callable check
circuit_breaker_service       contract  yes      import + callable check
check_run_contract_service    contract  yes      import + callable check
production_raw_payload_store  contract  no       gate 96/97 derivation
dry_run_runtime               runtime   yes      import + callable check
dry_run_worker                runtime   yes      import + callable check
scheduler_runtime             runtime   no       importlib.util.find_spec
background_worker             runtime   no       find_spec + console entry points
periodic_trigger              runtime   no       repo file scan
```

Neither dry-run component appears in `remaining_work`, and an invariant enforces
that. Having them does not move the system closer to monitoring, so listing their
absence as what is holding it back would be false progress.

## What Gate 100 may not change, and did not

```text
background_worker_available   false
production_worker_live        false
ready_to_start_monitoring     false
may_fetch_live_now            false   (all 5 Phase 1 sources)
may_schedule_monitor          false   (all 5 Phase 1 sources)
monitors_active               0
collectors_active             0
collector_status              not_active (all 5)
```

Three invariants hold the line, one in each patched service:

```text
dry_run_worker_read_as_a_background_worker      readiness
dry_run_worker_permitted_live_work:<source>     phase 1 policy
safe_to_schedule_on_a_dry_run_worker            activation preflight
```

The third was rewritten mid-gate. It first re-queried detection from inside the
invariant — validating the machine it ran on rather than the record it was handed
— and it disagreed with a Gate 98 test that simulated a scheduler runtime.
`background_worker_available` is now recorded on the preflight result and the
invariant reads that field. The Gate 98 simulation was completed to set both
halves, since a world where `_scheduler_runtime_available()` returns true is a
world with a worker in it.

## 100F artifacts

`artifacts/source_scheduler_dry_run_worker/`

```text
source_scheduler_worker_readiness.json
source_scheduler_dry_run_worker_result.json
source_scheduler_dry_run_worker_result.csv
source_scheduler_dry_run_worker_summary.md
```

Eight declarations on every file, stamped on every CSV row alongside
`runtime_mode`:

```text
dry_run_worker_available    true
background_worker_available false
production_worker_live      false
collectors_executed         false
urls_fetched                false
raw_payloads_written        false
source_monitoring_live      false
live_source_coverage        false
```

The first is the only true line and the one most easily misread. It means a
worker *contract* can consume a queue in-process; it does not mean a worker is
running, and the seven falses beneath it are what say so. They travel together
for that reason.

Built from the real queue over the five Phase 1 sources — every job blocked, every
reason attached. Deterministic against Gate 99F's fixed reference clock, so the
committed files match a fresh generation. The writer computes claim failures
first and refuses to write rather than emit a file whose declarations disagree
with the run behind them; verified by forging a declaration and by forcing a
side-effect claim, each of which leaves the directory absent.

## The production worker decision remains open

Gate 100A found the prerequisite nobody had written down: **there is no
long-running backend process.** The two running systemd units serve the frontend
and a tunnel; the API is started only by smoke scripts that kill it again; and
`main.py` has no lifespan hook.

So the ordering is:

```text
1  deploy_backend_process             deployment decision, no code behind it
2  choose_worker_topology             in-process (lifespan) or external
3  select_broker_if_external          only if external
4  add_periodic_trigger               a .timer in the repo is detected by 98E
5  configure_production_object_store  Gate 97's seam, deployed, round-tripped
```

All four topologies remain open, and two of them need no dependency at all:

```text
option                        needs                          dependency
in-process (FastAPI lifespan) a deployed backend process     none
systemd timer + oneshot CLI   a host, a unit, a timer        none
external worker + broker      a broker, a host, a deploy     celery/rq/arq + redis
platform scheduler            a platform                     none, or vendor SDK
```

A systemd timer firing Gate 99E's CLI would be a real periodic trigger, and Gate
98E already scans for `.timer` files in the repository — so that path becomes
detectable the day somebody checks one in.

`uv.lock` did not change in this gate, and neither did `pyproject.toml`.

## Unchanged human decisions

```text
- SAM.gov API key and role                    10/day without it
- 185 terms-queue items reviewed              148 + 62 + 4 + 1
- four SPA terms pages read by a human
- Simpler.Grants.gov tribal applicant_type enum
```

None is engineering, and none moved.

## Production boundary

```text
controlled customer pilot     NO_GO
production rollout            NO_GO
scheduler runtime             DRY RUN ONLY (dry_run_in_process)
dry-run worker                AVAILABLE (contract only, executes nothing)
background worker             NOT AVAILABLE
production worker             NOT LIVE - decision open
source monitoring live        0
collectors live               0
crawler live                  0
source coverage live          0
raw payload store production  NOT AVAILABLE
login live                    NO
production storage            NO
customer persistence          NO
pen-test passed               NO
65% improvement claimed       NO
```
