# 564 — Gate 101C: backend health and readiness contract

`src/nativeforge/services/backend_health_readiness_service.py`
`src/nativeforge/api/backend_runtime_routes.py`

Two questions that are routinely collapsed into one, kept apart:

```text
GET /backend/health      is this process up, and which code is it running?
GET /backend/readiness   what is this system allowed to do?
```

A process can be perfectly healthy and allowed to do almost nothing, which is
exactly the situation today. Answering both with one endpoint is how "the service
is green" comes to mean "we are in production".

## Why not /health

Gate 101A found a collision the brief did not anticipate. The Vite preview on
:5175 already serves a **static** `/health`, written by
`build_frontend_stamped.sh`:

```text
http://127.0.0.1:5175/health   ->  ok            (plain text, build stamp)
http://127.0.0.1:5175/version  ->  {"git_sha": "755d422...", "source_dirty": false, …}
backend /health                ->  {"status": "ok", "service": "nativeforge"}
```

The static one is up right now and answers `ok` whether or not a backend exists.
A monitor pointed at it would report the system healthy with no backend running
at all.

So the backend surface is `/backend/health`, the existing `/health` route is left
exactly as it was, and an invariant in both the runtime contract and the health
contract fails if the path is ever moved to `/health`. One question, one answer.

## Health

```text
status                 ok
service                nativeforge
git_sha                755d422201d5de0b4486c79fda7e7496b7220996
source_dirty           false
backend_runtime_mode   loopback_backend_contract
timestamp              2026-08-27T22:58:51+00:00
production_ready       false
```

`git_sha` and `source_dirty` are the same two facts the frontend build stamp
carries, which is what makes a mismatch detectable: if the SPA reports one sha
and the backend another, somebody deployed half a system.

Both are read via `git rev-parse` and `git status --porcelain`, and **any failure
reports `unknown` rather than raising**. A health endpoint that 500s because git
is missing is worse than one that admits it does not know which code it is
running. `source_dirty` is `None` rather than `False` when it could not be
checked — reporting `False` for "we did not look" would be claiming a clean tree
nobody inspected.

An invariant rejects a `git_sha` that is neither `unknown` nor forty hex
characters, so a plausible-looking placeholder like `main` fails rather than
passes.

`production_ready: False` is a constant, held by an invariant, so a caller
reading only this endpoint cannot infer readiness from a green status.

## Readiness

```text
backend_runtime_available              true    (a contract, not a process)
persistent_backend_live                false
database_ready                         detected live
production_raw_payload_store_available false
scheduler_runtime                      dry_run_in_process
background_worker_available            false
source_monitoring_live                 false
collectors_live                        0

blocked_reasons:
  background_worker_unavailable
  not_ready_to_start_monitoring
  persistent_backend_not_live
  production_raw_payload_store_unavailable
```

Every value is bridged from the service that owns it — Gate 98E for the
scheduler, Gate 96/97 for the payload store, Gate 101B for the backend — rather
than restated. A readiness endpoint maintaining its own copy of these facts would
drift from them, and the drift is always optimistic, because nobody notices a
green light that should be red.

`database_ready` is the one value this service determines itself, because
reachability is a genuine property of the moment. Any failure is `False`: an
unreachable database is not a ready one, and a health surface that raised on a
dead database would take the whole endpoint down with it.

## The boundaries readiness may not soften

```text
customer_auth_live         false
production_rollout         false
controlled_customer_pilot  false
live_source_coverage       false
live_fetch_performed       false
ready_to_start_monitoring  false
```

Each is a constant held by an invariant, and each has a parametrised test that
flips it and asserts the invariant fires. `collectors_live` must be exactly `0`.

## No secrets, checked structurally

Neither record may carry a key containing `password`, `secret`, `token`,
`api_key`, `credential`, `authorization`, `dsn`, `connection_string`,
`database_url`, `private_key` or `access_key`. `database_ready` is a boolean
about reachability, never a DSN.

The invariants scan key names on both records, a test scans both live response
bodies for credential markers, and a mutation adding a `database_password` field
to the readiness output was introduced and caught.

## Backend readiness is not customer auth, and not production rollout

A process that answers HTTP is a process that answers HTTP. It is not a login
system, it is not a pilot, and it is not a rollout. The three flags above say so
on every response, and they are the first thing a reader of this endpoint sees
after the blockers.
