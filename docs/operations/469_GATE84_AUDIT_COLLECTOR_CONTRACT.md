# 469 — Gate 84B: Audit event collector contract

`src/nativeforge/services/audit_event_collector_service.py`
(`nf_audit_event_collector_v1`).

## Why module-level `_AUDIT` was unsafe

Thirty services kept:

```python
_AUDIT: list[dict[str, Any]] = []

def _emit_audit(event: str, detail: dict[str, Any]) -> None:
    _AUDIT.append({"event": event, **detail})
```

The list lives for the life of the process. Four consequences, all real:

1. **Output depended on call history.** `audit_refs` is a tail slice
   (`_AUDIT[-3:]`). On a warm process it returned *other callers'* events — a
   service reporting an audit trail that was not its own.
2. **Unbounded growth.** Gate 83B measured every one of the thirty *doubling*
   per demo payload build. In a long-running process they never stop growing.
3. **Tests compensated instead of the design being right.** Twenty-four
   services shipped a `clear_*_audit_for_tests()` helper whose only job was to
   undo the accumulation, used at 29 call sites.
4. **Determinism needed a workaround.** Gate 83B cleared all thirty lists before
   each generation. That fixed the payload, not the design.

The deepest problem is semantic: an audit trail should belong to the operation
that produced it, not to whichever process happens to be running.

## How the request-scoped collector works

A collector instance owns its events, and **the caller defines the request
boundary**:

```python
def resolve_backup_restore(*, ..., collector: AuditEventCollector | None = None):
    collector = new_collector(collector)
    ...
    collector.add({"event": "restore_rehearsal", "non_prod": non_prod_rehearsed})
    return {..., "audit_refs": collector.event_names(3)}
```

A caller that passes nothing gets an isolated collector for that call. A caller
that wants one trail across three calls passes one collector to all three — the
sharing is explicit rather than implicit and process-wide.

### API

```text
record(event, detail=None) -> dict     record and return the stored event
add(entry) -> dict                     record an already-built event dict
snapshot() -> tuple[dict, ...]         immutable copy of everything
tail(count) -> list[dict]              last N, oldest first, no mutation
event_names(count=None) -> list[str]   the shape `audit_refs` has always had
has_event(*names) -> bool              membership without exposing the list
clear()                                resets *this* instance only
len(), iter(), bool()
describe() -> dict                     + collector_invariant_failures()
```

Reads never mutate: `snapshot` and `tail` copy, so a caller cannot tamper with
stored events through a returned reference. A test asserts this.

### Design rules the module holds to

- **No module-level mutable state of any kind** — not a list, not a registry,
  not a "current" collector. A test enumerates the module and fails on any
  list/dict/set global.
- **No singleton and no implicit default.** A shared instance is the bug being
  replaced.
- Cheap to instantiate per call, simple enough to use in thirty services.

### Deterministic ids

`event_id_factory` is an optional caller-supplied `(index, event) -> str`. Ids
are only stamped when a factory is given, and the factory comes from the caller
— never from a global clock or entropy source inside this module. That keeps it
compatible with `deterministic_demo_generation` without depending on it.

### `NoopAuditCollector`

Accepts events, keeps none. It is deliberately **not** the default anywhere:
silence has to be chosen explicitly, so an audit trail is never lost by
accident.

## What this module does not do

It records events; it does not persist them. Persistence remains
`security_audit_sink_service` and `repositories/audit_events`, neither of which
this gate touches.
