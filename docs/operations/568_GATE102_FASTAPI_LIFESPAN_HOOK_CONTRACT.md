# 568 — Gate 102C: FastAPI lifespan hook contract

`src/nativeforge/main.py`
`src/nativeforge/services/backend_lifespan_hook_service.py`

The attach point a future in-process scheduler would use, and a record that
nothing is attached to it.

## An attach point is not an attachment

```python
@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    record_startup()
    try:
        yield
    finally:
        record_shutdown()


app = FastAPI(title=settings.app_name, lifespan=lifespan)
```

Startup runs, shutdown runs, and between them the application does exactly what
it did before: serve HTTP. No scheduler is started, no collector is invoked, no
request goes out.

```text
scheduler_attached      false
collectors_started      false
urls_fetched            false
source_monitoring_live  false
```

All four are on the contract *and on every transition record*, so a test asserts
what the hook actually did rather than trusting a summary flag. A mutation making
startup claim a scheduler was attached was introduced and caught.

## Why add a hook that does nothing

Gates 100A and 101A both ended at the same wall: `main.py` had no lifespan hook,
so there was nowhere for an in-process background task to live even once a
process existed. Adding the attach point removes that wall without stepping over
it — cheap, reversible, and it takes one item off the remaining-work list without
pretending to take two.

It also makes the *absence* of a scheduler explicit and testable. Before, "no
scheduler runs at startup" was true because startup did not exist. Now it is true
because startup ran and deliberately started nothing, which is a claim a test can
check — and does, with sockets poisoned to raise.

## Both halves, or neither

`lifespan_hook_available` requires the hook to be **defined and passed to
FastAPI**. A defined-but-unwired lifespan is dead code that would report a
capability the application does not have.

That conjunction turned out to be invisible: both halves are true in the real
tree, so a mutation reducing it to just `defines_lifespan` survived every other
test. `detect_lifespan_hook_wired` now takes a `repo_root` so a test can point it
at a synthetic `main.py` that defines a lifespan and never hands it over — and a
second test covers the wired case, so neither is vacuous.

This is the fourth gate running where a defensive conjunct was untestable by
accident. The pattern is worth naming: **a conjunct whose partner is always true
in the current tree cannot be observed without a fixture that makes the partner
false.**

## The hook does not import the scheduler layer

`FUTURE_SCHEDULER_DEPENDENCIES` names the four services an in-process scheduler
would consult. They are recorded as a plan and **not imported** — importing them
at startup would make the application's boot depend on the scheduler layer for no
benefit. An AST test asserts none appears in the module's imports.

## What must be true before anything attaches

```text
persistent_backend_live                 gate 101B/102B - a proven process
background_worker_available             gate 98E - none exists
periodic_trigger_configured             gate 98E - none exists
production_raw_payload_store_available  gate 96/97 - not configured
```

All four appear in `blocked_reasons`, and an invariant fails if any is dropped
from the checklist — removing one would make the remaining work look shorter
than it is.

## Gate 102D: an in-process scheduler needs both halves

```text
in_process_scheduler_possible = persistent_backend_live and lifespan_hook_available
```

Gate 101 could only check the first, because the second did not exist. Both are
now checked in the scheduler readiness service, the worker decision service, and
the runtime contract, with an invariant in each.

A hook with nothing running is the easier half to mistake for progress, so that
is the case the tests force directly: a proven live backend with no attach point
in it must still report `in_process_scheduler_possible: false`.

And with **both** halves present, monitoring is still not live — no worker, no
trigger, no payload store. `ready_to_start_monitoring` stays false.
