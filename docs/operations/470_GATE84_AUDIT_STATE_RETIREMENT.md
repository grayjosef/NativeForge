# 470 — Gate 84C/D: Module audit state retirement

## Result

```text
services declaring `_AUDIT = []`      30  ->  0
appends to a module-level list        30  ->  0
`list(_AUDIT)` / `len(_AUDIT)` reads  24  ->  0
`clear_*_audit_for_tests()` helpers   24  ->  0
demo determinism `_AUDIT` reset       required  ->  removed
```

Four guard tests fail if any of these reappear.

## Services patched

All thirty. Two shapes:

**Family A (17) — `_emit_audit` helper.** The helper now takes the collector as
its first argument, and every public function that emits takes an optional
`collector` and creates one when not supplied:

```python
def _emit_audit(
    collector: AuditEventCollector, event: str, detail: dict[str, Any]
) -> None:
    collector.record(event, detail)
```

**Family B (13) — append inside one public function.** The function creates a
collector and reads its own tail. Purely local.

**Four aggregating readers** needed the request boundary drawn explicitly,
because they call emitting sub-functions and then read the aggregate:
`run_source_freshness_bundle`, `run_source_probe_bundle`,
`build_object_storage_adapter_status`, and
`run_session_tenant_enforcement_suite`. Each creates one collector and threads
it into every sub-call it makes.

## What audit behaviour is preserved

**Every event still fires, with the same name and the same detail.** Nothing was
dropped and nothing was silenced.

Two services (`auth0_login_rbac_validation`, `session_tenant_enforcement`)
recorded an extra `"at"` timestamp inside `_emit_audit`. The first pass of the
mechanical transform replaced their helper with the generic one-liner and
**dropped that field**. It was caught by an unused-import warning
(`datetime` and `uuid` suddenly unused) and restored; a Gate 84 test now asserts
every event from those services still carries `at`.

### What legitimately changed

`audit_refs` now contains only the events *this call* emitted. Previously, on a
warm process, a tail slice returned up to N events including earlier callers'.

That difference is the bug being fixed, not a loss: the events are still
emitted and still reachable through the collector. A service simply stops
reporting an audit trail that was not its own.

Concretely, one test had been asserting on the leak.
`test_freshness_gates` called `resolve_source_health()` five times standalone and
then asserted `run_source_freshness_bundle(rows=[...])["audit_refs"]` was
non-empty — which only passed because the module list still held those five
calls' events. The test now creates one collector and passes it to the calls it
means to group, which is what it was implicitly relying on all along.

### Payload impact

Regenerating the committed demo payload changed exactly **two** fields:

```text
session_tenant_enforcement.denial_audit_events            true
session_tenant_enforcement.suite.denial_audit_events_present  true
```

Both stayed `true` — but only after a fix. The first threading pass created the
suite's collector and then failed to pass it to any sub-call, so the suite could
not see its own denial events and both flipped to `false`. That is precisely the
kind of silent audit loss this gate forbids, and it was caught by the payload
diff. Both are now `true` and a test asserts the suite still detects its own
denial events.

Everything else in the payload is byte-identical.

## Caller compatibility

No production caller ever read the deleted helpers — all 29 call sites were in
`tests/`, and they existed to compensate for the global.

- `clear_*_audit_for_tests()` calls were removed: with request-scoped state
  there is nothing to reset.
- The seven tests that asserted on audit events now create a collector, pass it
  to the calls they care about, and assert on it. That is more honest than the
  previous version, which asserted on whatever the process had accumulated.
- Every new `collector` parameter is keyword-only and optional, so any caller
  that does not care is unaffected.

## Determinism workaround removed

`demo_payload_determinism_service.ACCUMULATOR_ATTRS` was `("_AUDIT",)` and is
now `()`.

**The mechanism is kept, not deleted.** It is the seam that would catch the next
module-level accumulator, and an empty tuple is a claim — "nothing needs
resetting" — that a test checks stays true. A second test exercises the reset
machinery against a stand-in attribute so it does not rot now that its last real
user is gone.

The clock, uuid and artifact-path parts of the determinism context are
**unchanged**; those still matter, and the payload is still byte-identical
across processes.

## What remains blocked

- **`_LOCAL_DEV_STORE`** in `production_metadata_adapter_service` is a
  module-level dict serving as a local dev store. It is a store rather than an
  audit accumulator and is out of this gate's scope, but it is the same class of
  process-lifetime state and still has a `clear_*_for_tests()` helper.
- **`nm_wa_operator_demo.json`** was never audited for the determinism or
  accumulation problems.
- Everything the campaign already had blocked: robots/terms review, primary
  source verification, PDF parser decision, real OIDC credentials, managed
  Postgres, migration 0028, backup/restore, pen test.
