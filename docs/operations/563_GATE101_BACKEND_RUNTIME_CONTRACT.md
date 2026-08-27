# 563 — Gate 101B/D: backend runtime contract

`src/nativeforge/services/backend_runtime_contract_service.py`
`deploy/systemd/nativeforge-backend.service`

Answers whether NativeForge has a persistent backend runtime. It starts no
process, binds no socket, and makes no request.

## The contract today

```text
runtime_mode                      loopback_backend_contract
backend_runtime_available         true
backend_runtime_contract_available true
persistent_backend_live           false
loopback_only                     true
host                              127.0.0.1
port                              8000
healthcheck_path                  /backend/health
trust_endpoint_available          false
lifespan_hook_available           false
systemd_unit_available            true
systemd_unit_installed            false
systemd_unit_enabled              false
```

Two lines are true and both are narrow. A unit *template* is checked into the
repository and it binds loopback only. Nothing is installed, nothing is enabled,
and nothing is running.

## Five modes, and the one that has to be earned

```text
none                         no app, no way to run it
smoke_script_only            the API runs, but only inside a script that
                             backgrounds it and kills it on exit
loopback_backend_contract    a unit template exists, loopback-bound, not installed
loopback_backend_configured  a unit is installed on the host
persistent_backend_live      a long-running process is actually serving
```

`smoke_script_only` is the state Gate 100A found, and it deliberately does **not**
count as a backend runtime. Four scripts start the API:

```text
scripts/m0_demo_up.sh
scripts/m8_close_gate_staging_smoke.sh
scripts/la_scale_federal_staging_verify.sh
scripts/seed_hygiene_staging_verify.sh
```

Every one backgrounds it and kills it on the `trap`. A process that exists for
eleven seconds inside a smoke script is not something a scheduler can live in,
and an invariant fails any result where that mode reads as available.

## persistent_backend_live requires proof, and proof means an observation

Every other mode is established by reading files. This one is not: a template can
be read and a unit file can be read, but *running* is a property of the host at a
moment in time.

So it requires a `process_proof` that says what was seen:

```python
{"observed": True, "pid": 4242, "observed_at": "2026-01-01T12:00:00+00:00"}
```

Missing any field, or `observed: False`, is not a proof. `build_backend_runtime_
contract` never goes looking for one on its own, because a service that probed
for a listener would be doing I/O to answer a question about itself.

Nothing in this gate supplies one. Six parametrised cases cover the incomplete
forms, and one covers the complete form — which does reach
`persistent_backend_live`, so the refusal is a derivation rather than a constant.

## Loopback is the line that actually matters

The Cloudflare tunnel on this host is already running and already reachable. A
backend bound to `0.0.0.0` would be published through it.

So `loopback_only` is derived from the host rather than declared, an invariant
fails any contract whose host is not loopback, and a second invariant fails if
the unit template's `ExecStart` does not bind `127.0.0.1`. A test parses the
template directly and asserts `0.0.0.0` appears nowhere in it; another test feeds
the detector a deliberately public template and confirms it says so, so the check
is not vacuously true.

## The systemd unit template

`deploy/systemd/nativeforge-backend.service` — **not installed, not enabled.**

```text
WorkingDirectory=/home/josefgray/projects/nativeforge
ExecStart=.../uvicorn nativeforge.main:app --host 127.0.0.1 --port 8000
EnvironmentFile=-/home/josefgray/projects/nativeforge/.env
Restart=on-failure  RestartSec=5  StartLimitBurst=5/300s
NoNewPrivileges  PrivateTmp  ProtectSystem=full  ProtectHome=read-only
```

No credential is inlined. The `EnvironmentFile` is optional (`-`), is not in the
repository, and is not created by this gate. A test scans the unit's
**directives** — not its comments — for credential markers, and asserts no inline
`Environment=` line exists.

That test needed correcting once: its first version scanned the whole file and
failed on the unit's own comment, "No secrets in this unit". That is the Gate 93
defect where a guard fires on its own disclaimer. It now strips comment lines and
carries a poisoned-input check so it cannot pass vacuously.

`Restart=on-failure` with a start limit rather than `always`: a backend that
cannot start should stop and be visible, not thrash quietly.

## A backend is not the things it gets confused for

```text
a backend runtime is NOT   collectors being live
a backend runtime is NOT   a scheduler running
a backend runtime is NOT   customer auth being live
a backend runtime is NOT   production rollout
```

All four are False on every result, none is derived from the runtime mode, and
three tests assert them against a contract in the strongest mode this service can
reach — `persistent_backend_live` with a full proof — so the separation holds
even where it would be most tempting to blur.

## What must happen next

```text
1  install_backend_systemd_unit       a host decision; nothing in the repo does it
2  prove_a_long_running_process       live needs an observation, not a file
3  add_a_lifespan_hook                main.py has none; an in-process scheduler
                                      still has nowhere to attach
4  configure_production_object_store  Gate 97's seam, before any check may run
```

An invariant fails any result where this sequence has been reordered or
truncated.
