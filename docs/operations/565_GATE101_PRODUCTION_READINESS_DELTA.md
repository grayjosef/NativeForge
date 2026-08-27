# 565 — Gate 101E/F: production readiness delta

## What changed

Gate 100 reported:

```text
runtime_mode                  dry_run_in_process
scheduler_runtime_available   true
dry_run_worker_available      true
background_worker_available   false
production_worker_live        false
source_monitoring_live        false
ready_to_start_monitoring     false
```

Gate 101 reports:

```text
runtime_mode                       dry_run_in_process
backend_runtime_mode               loopback_backend_contract   <- new
backend_runtime_contract_available true                        <- new
persistent_backend_live            false                       <- new
in_process_worker_possible         false                       <- new
scheduler_runtime_available        true
dry_run_worker_available           true
background_worker_available        false
production_worker_live             false
source_monitoring_live             false
ready_to_start_monitoring          false
```

Four facts were added. Nothing that was false became true.

## persistent_backend is a component, and it blocks

```text
component                     kind      present  detected by
schedule_decision_service     contract  yes      import + callable check
circuit_breaker_service       contract  yes      import + callable check
check_run_contract_service    contract  yes      import + callable check
production_raw_payload_store  contract  no       gate 96/97 derivation
dry_run_runtime               runtime   yes      import + callable check
dry_run_worker                runtime   yes      import + callable check
persistent_backend            runtime   no       gate 101B contract
scheduler_runtime             runtime   no       importlib.util.find_spec
background_worker             runtime   no       find_spec + console entry points
periodic_trigger              runtime   no       repo file scan
```

Unlike the two dry-run components, `persistent_backend` **is** in
`RUNTIME_COMPONENT_KEYS` and therefore appears in `remaining_work`. That is the
difference: having a dry-run worker does not move the system closer to
monitoring, but having a backend process does — an in-process scheduler needs a
process to be in.

## source_monitoring_live gained a fourth conjunct

```python
source_monitoring_live = (
    runtime_mode in LIVE_RUNTIME_MODES
    and background_worker_available
    and periodic_trigger_available
    and persistent_backend_live          # Gate 101E
)
```

A scheduler with nowhere to run is not monitoring, however live the other three
look.

That conjunct needed a test built specifically to see it. With `runtime_mode`
never live today, every conjunct after the first is unobservable, and a mutation
dropping this one survived the whole file. There is now a test that forces the
one world which distinguishes them — a live mode, a worker, a trigger, and no
backend — and asserts the answer is still false. This is the second gate running
where a defensive conjunct turned out to be untestable by accident; both are now
tested directly rather than left to look correct.

## What Gate 101 may not change, and did not

```text
persistent_backend_live       false
background_worker_available   false
production_worker_live        false
ready_to_start_monitoring     false
may_fetch_live_now            false   (all 5 Phase 1 sources)
may_schedule_monitor          false   (all 5 Phase 1 sources)
monitors_active               0
collectors_active             0
collector_status              not_active (all 5)
customer_auth_live            false
production_rollout            false
```

Four invariants hold the line, one in each patched service:

```text
monitoring_live_without_a_persistent_backend        scheduler readiness
in_process_possibility_disagrees_with_the_backend   worker decision
scheduling_without_a_persistent_backend             phase 1 policy
safe_to_schedule_without_a_persistent_backend       activation preflight
```

Each reads a **recorded field** rather than re-querying detection — the
correction made in Gate 100, applied here from the start.

## A defect this gate found in three earlier services

The Gate 98, 99 and 100 artifact writers passed their *output* directory into
`build_scheduler_readiness(repo_root=...)` as the *inspection* root. That was
harmless while the only repo-scanning detector was `periodic_trigger`, which
found nothing in a temp directory and nothing in the real repo — the same answer
either way.

Gate 101's `persistent_backend` detection reads the unit template, so a
determinism check writing into a temp directory suddenly described an empty tree:

```text
real root  -> backend_runtime_mode: loopback_backend_contract
temp root  -> backend_runtime_mode: none
```

Three committed artifact sets stopped matching a fresh generation, for a reason
that had nothing to do with their content. All four writers now take a separate
`detect_root` that defaults to the real repository, so *where the files go* and
*what gets described* are independent. The Gate 101 writer had the same bug on
its first run and was fixed the same way.

## 101F artifacts

`artifacts/backend_runtime_readiness/`

```text
backend_runtime_readiness.json
backend_runtime_readiness.csv
backend_health_contract.json
backend_systemd_unit_contract.json
backend_runtime_readiness_summary.md
```

Seven declarations on every file, stamped on every CSV row alongside
`runtime_mode`:

```text
backend_runtime_contract_available  true
persistent_backend_live             false
source_monitoring_live              false
collectors_live                     0
live_fetch_performed                false
live_source_coverage                false
customer_auth_live                  false
```

The first is the only true one and the one that would be misread. It means a
loopback unit *template* is checked into the repository — not that a backend is
running, and not that one is installed.

Two things are deliberately kept out of the committed artifacts:

- **The live git sha.** `backend_health_contract.json` documents the contract's
  shape and carries one worked example built from forty zeroes, labelled
  `example_only`. A real sha would make the committed file stale on the very next
  commit, and `source_dirty` flips the moment the tree is clean.
- **`database_ready`.** It is a property of the host at a moment; committing it
  would make the file disagree with a fresh generation on a machine with no
  database. The live endpoint reports it.

`backend_systemd_unit_contract.json` carries `installed_by_this_gate: false` and
`enabled_by_this_gate: false`. Those are not detections of the host — this
service never inspects systemd — they are statements about what this gate did.

The writer refuses rather than annotates, and one of its refusals is specifically
a template that does not bind loopback only.

## What remains

### Engineering

```text
- install the backend systemd unit    host decision; nothing in the repo does it
- prove a long-running process        live needs an observation
- add a lifespan hook to main.py      an in-process scheduler still cannot attach
- a background worker                 Gate 100's open decision
- a periodic trigger
- an object store deployment          Gate 97's seam
```

`uv.lock` and `pyproject.toml` did not change. `fastapi` and `uvicorn[standard]`
were already declared, so nothing new was needed to describe or run a backend.

### Unchanged human decisions

```text
- SAM.gov API key and role                    10/day without it
- 185 terms-queue items reviewed              148 + 62 + 4 + 1
- four SPA terms pages read by a human
- Simpler.Grants.gov tribal applicant_type enum
```

## Production boundary

```text
controlled customer pilot     NO_GO
production rollout            NO_GO
backend runtime contract      AVAILABLE (template only, loopback, not installed)
persistent backend            NOT LIVE
scheduler runtime             DRY RUN ONLY (dry_run_in_process)
dry-run worker                AVAILABLE (contract only)
background worker             NOT AVAILABLE
production worker             NOT LIVE
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

**No live backend systemd service was enabled by this gate**, no collector ran,
no URL was fetched, no raw payload was written, no monitoring started, and no
source coverage is claimed. Backend readiness is not customer auth, and it is not
production rollout.
