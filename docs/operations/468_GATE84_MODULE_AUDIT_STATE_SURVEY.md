# 468 — Gate 84A: Module-level `_AUDIT` state survey

Surveyed before patching. Counts are from AST analysis, not grep alone, so each
append site is mapped to the function that encloses it.

## Inventory

```text
services declaring `_AUDIT: list[dict[str, Any]] = []`   30
append sites                                             30   (exactly one each)
tail-slice reads feeding `audit_refs`                     7
`list(_AUDIT)` reader helpers                            22
`_AUDIT.clear()` test-reset helpers                      24
`len(_AUDIT)` exposed as `audit_events_emitted`           2
membership scan over `_AUDIT`                             1
```

## Why this is unsafe

The list lives for the life of the process, so:

- **Output depends on call history.** `audit_refs` is a tail slice
  (`_AUDIT[-3:]`), so its contents depend on what earlier calls appended — in
  the same process, possibly from a different service concern.
- **Memory grows without a request boundary.** Gate 83B measured every one of
  the thirty *doubling* per demo payload build.
- **Tests must compensate.** Twenty-four services ship a
  `clear_*_audit_for_tests()` helper that exists only to undo the accumulation,
  and 29 test call sites use it.
- **Determinism needed a workaround.** Gate 83B's context clears all thirty
  lists per generation. That fixes the payload, not the design.
- **Audit semantics are wrong.** An audit trail should belong to the operation
  that produced it, not to whichever process happens to be running.

## The two families

### Family A — 22 services: `_emit_audit` helper + reader/clearer API

```python
_AUDIT: list[dict[str, Any]] = []

def _emit_audit(event: str, detail: dict[str, Any]) -> None:
    _AUDIT.append({"event": event, **detail})

def get_x_audit_events() -> list[dict[str, Any]]:
    return list(_AUDIT)

def clear_x_audit_for_tests() -> None:
    _AUDIT.clear()
```

`_emit_audit` is called from several public functions, and the getter aggregates
across all of them. Tests call two or three public functions and then read the
getter — so the *request* legitimately spans several calls.

Services: `auth0_login_rbac_validation`, `customer_data_policy`,
`gate25_object_storage_unlock`, `gate25_storage_approval_metadata`,
`gate26_controlled_pilot_master`, `gate26_security_attestation`,
`gate27_cutover_claim_freeze`, `gate27_owner_unlock_packet`,
`gate28_dry_run_cutover`, `gate28_mode_b_rehearsal`, `gate29_auth0_real_input`,
`gate29_storage_security_real_input`, `gate30_final_closeout`,
`object_storage_signed_url`, `production_metadata_adapter`,
`retention_delete_export`, `session_tenant_enforcement` (+ the five gate31/32
services that also expose a clearer).

### Family B — 8 services: append inside one public function

```python
def resolve_backup_restore(...):
    _AUDIT.append({"event": "restore_rehearsal", ...})
    ...
    "audit_refs": [a["event"] for a in _AUDIT[-3:]],
```

The append and the tail slice sit in the same call, so the only cross-call
leakage is the tail picking up *previous* calls' events. Request scoping makes
these strictly more correct.

Services: `gate31_live_authority`, `gate31_live_source_coverage`,
`gate31_pilot_onboarding`, `gate31_support_triage`, `gate32_backup_restore`,
`gate32_launch_packet`, `gate32_observability`, `gate32_source_freshness`,
`gate33_healthcheck`, `gate33_restore_rehearsal`, `gate33_runbook`,
`gate33_source_probe`, `gate34_owner_wait`.

## Outputs that expose audit data

| Service | Field | Shape |
| --- | --- | --- |
| `gate31_live_authority` | `audit_refs` | `_AUDIT[-3:]` event names |
| `gate31_live_source_coverage` | `audit_refs` | `_AUDIT[-3:]` |
| `gate31_support_triage` | `audit_refs` | `_AUDIT[-3:]` |
| `gate32_backup_restore` | `audit_refs` | `_AUDIT[-3:]` |
| `gate32_source_freshness` | `audit_refs` | `_AUDIT[-5:]` |
| `gate33_restore_rehearsal` | `audit_refs` | `_AUDIT[-5:]` |
| `gate33_source_probe` | `audit_refs` | `_AUDIT[-8:]` |
| `object_storage_signed_url` | `audit_events_emitted` | `len(_AUDIT)` |
| `production_metadata_adapter` | `audit_events_emitted` | `len(_AUDIT)` |
| `session_tenant_enforcement` | suite check | membership scan over `_AUDIT` |

**Expected output change.** With request scoping, a tail slice returns only the
events this call emitted. Today, on a warm process, it returns up to N events
including earlier callers'. That difference *is* the bug being fixed — the
events themselves are still emitted and still reachable, they simply stop
leaking into an unrelated call's output.

The committed demo payload should be **unaffected**: Gate 83B's determinism
context already clears every list before a generation, so each service is
called once with an empty list and its `audit_refs` already reflects only that
generation. This is checked, not assumed.

## Demo-only vs runtime/live path

None of the thirty is on a live customer path today — production storage,
customer persistence and login are all NO_GO, and these services model gate
readiness rather than serve requests. But they are **not** demo-only either:
they are ordinary services that the demo bridge happens to call, and several
(`session_tenant_enforcement`, `object_storage_signed_url`,
`retention_delete_export`) model exactly the paths that *will* be live.

That is the argument for fixing the design rather than leaving the Gate 83B
workaround: the accumulation bug would otherwise ship into the first thing that
runs these per request.

## Tests depending on accumulated state

29 call sites across ~24 files, all in `tests/`. **No production caller reads
these getters.** The pattern is:

```python
clear_x_audit_for_tests()      # undo previous tests' accumulation
result = build_x(...)
assert any(e["event"] == "..." for e in get_x_audit_events())
```

The clearer exists solely to compensate for the global. Once state is
request-scoped, both the clearer and the module-level getter lose their reason
to exist.

## Patch plan

1. **`audit_event_collector_service`** — a small collector owning its own
   events. No module-level list, no singleton.
2. **Family B** — create a collector at the top of the single public function
   and read the tail from it. Purely local.
3. **Family A** — `_emit_audit(collector, event, detail)`; every public function
   that emits takes an optional `collector` parameter and creates one when not
   supplied. **The caller defines the request boundary**, which is the honest
   model: a test that wants events from three calls passes one collector to all
   three.
4. **Delete** `get_*_audit*()` and `clear_*_for_tests()`. Their behaviour is
   replaced by passing a collector in, and leaving them would leave an API that
   silently returns nothing.
5. **Update the 29 test call sites** to inject a collector.
6. **Reduce the determinism workaround** — drop `_AUDIT` from
   `ACCUMULATOR_ATTRS`. Keep the clock, uuid and artifact-path parts, which
   still matter.
7. **Guard tests** — no module-level `_AUDIT` may reappear; repeated calls must
   not grow `audit_refs`; two calls must not see each other's events.

## Not in scope

- `SECURITY_AUDIT_ACTIONS` / `UNPERSISTABLE_AUDIT_ACTIONS` in `domain/enums.py`
  are frozensets of vocabulary, not accumulators.
- `security_audit_sink_service` and `repositories/audit_events.py` are the real
  audit persistence path and hold no module-level list.
- No audit event content changes. No event is dropped.
