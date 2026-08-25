# 464 — Gate 83B-A: Demo payload determinism survey

## Generator command

```python
from nativeforge.services.sc_monday_demo_bridge_service import (
    build_sc_customer_demo_bridge_payload,   # composes ~61 surfaces
    write_sc_customer_demo_bridge_json,      # -> frontend/src/demo/sc_customer_demo.json
)
```

Two consecutive in-process builds were diffed leaf by leaf, and every mutable
module global under `nativeforge.` was snapshotted around a build.

## Fields that differ

**94 differing leaves across 29 of the 61 surfaces.**

By key name:

```text
15  probe_run_id          8  event_id            2  audit_events_emitted
13  created_at            8  timestamp           2  preview_generated_at
10  nonce                 5  audit_refs          2  pentest_run_id
 5  feedback_report_id    4  run_id              2  storage_run_id
 2  auth_run_id           2  closeout_run_id     2  rehearsal_run_id
 1  validated_at  1  checked_at  1  last_checked_at  1  updated_at
 1  no_secret_log_path  1  sample_evidence_intake_id  ...
```

Worst-affected surfaces: `audit_operator_storage` (16), `evidence_lifecycle`
(16), `source_probes` (16), `oidc_live_path` (8), `feedback_loop` (5).

Representative values:

```text
$.evidence_lifecycle.flow.audit_events[0].timestamp
  a="2026-08-25T10:30:57.607969+00:00"   b="2026-08-25T10:31:02.952986+00:00"

$.audit_operator_storage...sample_events[0].nonce
  a="fdac5a11"                            b="94b5ad2c"

$.auth0_live_validation.validation_run.run_id
  a="nf_auth0_live_val_20260825T103058Z_98c4843b"
  b="nf_auth0_live_val_20260825T103103Z_6ccd1f92"

$.backup_restore.result.audit_refs[len]
  a=1                                     b=2          <-- not a clock or a random
```

## Three distinct causes

### 1. Wall clock

Leaf services call `datetime.now(UTC)` directly. There is **no shared `now()`
helper** — 139 service files call it, 41 of which are loaded during a demo
build. Timestamps also get embedded inside generated ids
(`nf_auth0_live_val_20260825T103058Z_...`), so a clock fix repairs part of the
id churn too.

### 2. Randomness

`uuid.uuid4().hex[:8]` supplies nonces, event ids and id suffixes. 37 loaded
modules expose `uuid`.

Confirmed **not** in play: `secrets`, `random`, `time` — zero loaded
`nativeforge.` modules expose any of them, which keeps the patch surface small.

### 3. Module-global accumulators — the one that is not just noise

Thirty services hold a module-level list:

```python
_AUDIT: list[dict[str, Any]] = []
...
_AUDIT.append({...})
...
"audit_refs": [a["event"] for a in _AUDIT[-3:]],
```

Snapshotting around a build shows **every one of them doubling**:

```text
gate26_controlled_pilot_master_service._AUDIT:  13 -> 26
gate32_source_freshness_service._AUDIT:         15 -> 30
gate33_source_probe_service._AUDIT:             15 -> 30
session_tenant_enforcement_service._AUDIT:      13 -> 26
... 30 modules in total
```

This is worse than nondeterminism. The payload depends on **how many times the
process has already built one** rather than on its inputs, and the lists grow
without bound in any long-running process — a slow memory leak that happens to
be invisible because these services are normally called once per process.

A clock and uuid fix alone would **not** repair `audit_refs`; the accumulators
have to be reset per generation.

## Deterministic seams available

Every leaf uses the same two import shapes:

```python
import uuid                       # module attribute `uuid` on the service module
from datetime import UTC, datetime  # module attribute `datetime` = the class
```

Both are ordinary module attributes, so both can be swapped for the duration of
a generation and restored afterwards. The `_AUDIT` lists are likewise module
attributes and can be cleared and restored.

Counts among loaded modules after a build: `datetime` 41, `uuid` 37,
`_AUDIT` 30.

## Unsafe seams — rejected

**Threading a seed/clock parameter through the services.** This was the obvious
reading of "patch the assemblers", and it is the wrong trade here:

- it would touch 40+ services and their signatures for a demo-only concern;
- those services also run outside demo generation, so a demo parameter would
  become part of their runtime API;
- it is easy to miss one, and a miss is silent — the payload simply keeps
  churning in one field nobody notices.

**Editing the generated JSON by hand.** Forbidden by the gate, and it would
decouple the artifact from its generator.

**Making the services stop recording audit events.** That would remove real
behaviour to make a demo reproducible.

**Rewriting `_AUDIT` to be request-scoped everywhere.** Correct long-term, but
it is a 30-service refactor of live audit code, and doing it inside a demo
determinism gate would put runtime audit behaviour at risk for a presentation
concern. Recorded as engineering-blocked instead.

## Patch plan

One context manager, `deterministic_demo_generation()`, entered **only** by the
demo generator and the determinism verifier:

1. Freeze the clock — replace `mod.datetime` with a fixed-`now()` subclass on
   every loaded `nativeforge.` module where that attribute is the real class.
2. Seed identity — replace `mod.uuid` with a shim whose `uuid4()` is a
   counter-derived, seed-namespaced value.
3. Reset accumulators — clear every module-level `_AUDIT` list on entry.
4. Restore all three exactly on exit, including on exception.

Why a scoped context rather than per-service edits: it cannot miss a service, it
touches no service signature, and it has **zero runtime impact by construction**
— nothing at runtime enters the context. A test asserts the real primitives are
restored afterwards.

The residual risk is that the context patches module attributes process-wide
while active. It is mitigated by being narrowly scoped, exception-safe, and
covered by a restoration test.
