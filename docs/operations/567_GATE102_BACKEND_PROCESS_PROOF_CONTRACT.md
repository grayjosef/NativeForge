# 567 — Gate 102B: backend process proof contract

`src/nativeforge/services/backend_process_proof_service.py`

Captures evidence that a persistent backend process is running, and refuses to
call it live on anything less.

## Why a proof and not a detection

Every other capability in this campaign is established by reading files: a module
imports, a template exists, a package is installed. Running is different. It is a
property of one host at one moment, and it stops being true the instant the
process exits.

So this produces a **dated observation** rather than a standing fact, and the
service never goes looking — every input is supplied by whoever did the
observing. A service that probed for a listener would be doing I/O to answer a
question about itself, and its answer would change under a test that never asked
for a network call. An AST test asserts it imports no HTTP client.

## Five requirements, each independently disqualifying

```text
observed_at    an undated observation is not evidence of anything
unit_active    systemd reports the service running
pid            a process id was actually seen
loopback host  127.0.0.1 / ::1 only
healthcheck    /backend/health answered ok
```

Failing any one leaves `persistent_backend_live` false with a stated reason.
Fifteen parametrised cases cover the failure forms, and one covers the complete
form — so the refusal is a derivation rather than a constant.

The healthcheck matters more than it looks. **A unit can be `active` while the
application inside it fails every request.** systemd knows the process exists,
not that it works. Requiring the endpoint to answer is the difference between
"something is running" and "the backend is running", and `HEALTHCHECK_SATISFYING`
is `{"ok"}` — `unknown` is the honest answer when nobody looked, and it does not
satisfy anything.

A sixth check catches an impossible report: `unit_active` with
`unit_installed` false. systemd cannot run a unit it does not have.

## source_dirty is deliberately not disqualifying

A tree with uncommitted changes blocks *production readiness*. It does not block
the observation that a process exists — the process is running whatever code it
is running, and pretending otherwise would make the proof less accurate rather
than more careful.

So `source_dirty` is recorded, `production_ready` is False regardless, and
`persistent_backend_live` is left alone. Conflating the two would mean a
developer with an unsaved file could not observe their own running server. A
mutation making dirty source unmake the observation was introduced and caught.

## A proof is not a licence

```text
collectors_live         0
source_monitoring_live  false
scheduler_attached      false
live_fetch_performed    false
```

None is derived from the proof, all are held by invariants, and the tests assert
them against a **complete, passing** proof — the state where blurring them would
be most tempting.

## The bridge to Gate 101B

`as_runtime_contract_proof` returns the `{observed, pid, observed_at}` shape the
runtime contract expects, **or `None`** when the proof does not support a live
backend. A weak proof cannot be handed upward and quietly satisfy it, and a test
covers both directions.

## What was observed on this host

```text
observed_at         2026-08-28T01:54:22+00:00
unit_name           nativeforge-backend.service
unit_installed      true
unit_enabled        false      <- operator approved start, not enable
unit_active         true
pid                 81370
host                127.0.0.1
port                8000
loopback_only       true
healthcheck_status  ok
readiness_status    ok
git_sha             5e676eb...
source_dirty        true       <- the gate's own uncommitted work
persistent_backend_live  true
```

The unit binds loopback only, confirmed twice: `ss` shows
`127.0.0.1:8000`, and a request to this host's LAN address is refused.

**This observation is not committed.** It carries a pid, a timestamp and a live
healthcheck result — all properties of this machine at that minute. Committed
artifacts are compared against a fresh generation by test, so any of them would
fail that comparison elsewhere, and here minutes later. The artifacts carry the
contract and a fixed worked example; the observation lives in the gate report
and `/tmp/nativeforge-gate102-process-proof.json`.
