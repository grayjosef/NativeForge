# 559 — Gate 100B: worker runtime decision contract

`src/nativeforge/services/source_worker_runtime_decision_service.py`

Records which worker boundary has been selected and what is still missing. It
starts nothing.

## The decision

```text
runtime_mode                 dry_run_in_process
worker_runtime_available     true
background_worker_available  false
production_worker_live       false
dry_run_worker_available     true
external_worker_required     true
dependency_required          false
dependency_selected          none
broker_required              true
broker_selected              none
systemd_unit_required        true
systemd_unit_configured      false
```

Two lines are true and both are narrow. `worker_runtime_available` means an
in-process dry-run runtime exists; `dry_run_worker_available` means it can
consume a queue. Neither is a background worker, and `external_worker_required`
sitting at true beside them is the point — **needing a worker is not having
one**, and the two facts are reported separately so neither can stand in for the
other.

## Five modes, and one of them is not a detection

Gate 99D built a detection ladder. This gate adds a fifth mode that evidence
cannot produce:

```text
none                        nothing at all                        detected
dry_run_in_process          a queue can be built here             detected
external_worker_required    a worker is needed, none is chosen    DECIDED
external_worker_configured  a worker exists, not proven live      detected
production_worker_live      a worker is running and consuming     detected
```

`external_worker_required` is a statement about intent. No amount of inspection
finds it, because it is the conclusion a person reached *after* inspecting. So
`DETECTED_RUNTIME_MODES` is imported from Gate 99 rather than restated, this
module declares only `DECISION_ONLY_RUNTIME_MODES`, and an invariant fails if the
two sets ever overlap — which would mean the distinction had quietly dissolved.

## The prerequisite the brief does not mention

Gate 100A found **no long-running backend process**. The two running systemd
units serve the frontend and a tunnel; the API is started only by smoke scripts
that background it and kill it again; and `main.py` has no lifespan hook.

So an in-process worker has nowhere to live, and an external worker would be
infrastructure for a service that is not deployed. `next_required_actions`
reports the ordering, and an invariant fails any result where it has been
reordered or truncated:

```text
1  deploy_backend_process            no persistent backend exists
2  choose_worker_topology            in-process or external
3  select_broker_if_external         only if external; a timer needs none
4  add_periodic_trigger              a .timer in the repo is detected by 98E
5  configure_production_object_store Gate 97's seam, deployed and round-tripped
```

Step 1 first is not pedantry. Choosing a broker before there is a process to run
it buys infrastructure — and lock-in — for a service nobody is running.

## No dependency, and `uv.lock` is unchanged

```text
pyproject.toml:12   "fastapi>=0.115"
pyproject.toml:13   "uvicorn[standard]>=0.32"
```

An ASGI server is already declared, so an in-process worker needs nothing new.
`DRY_RUN_WORKER_REQUIRES_DEPENDENCY` is `False`, and an invariant fails any
result claiming otherwise — the dry-run worker must never be the thing that
pulls a broker into the project.

A dependency becomes required only behind a *selected* broker for an *external*
worker, and both halves are checked. Selecting `none_systemd_timer` — a real
option, and the cheapest one — drops `broker_required` and `dependency_required`
to false.

## Five brokers recorded, none selected

```text
redis  rabbitmq  postgres_queue  sqs  none_systemd_timer
```

Listed so the choice reads as *open* rather than as *absent*. An unrecognised
value resolves to no selection rather than being accepted.

## Nothing here implies monitoring

`source_monitoring_live` is False on every decision and is never derived from
the mode. Even `production_worker_live` — which this gate cannot reach — would
mean a worker is consuming jobs, not that a source is being watched. Gate 98F
exists because those two were once conflated, and this service does not repeat
it.

`collectors_executed`, `urls_fetched`, `raw_payloads_written`,
`live_source_coverage` and `worker_started` are all False, all held by
invariants.
