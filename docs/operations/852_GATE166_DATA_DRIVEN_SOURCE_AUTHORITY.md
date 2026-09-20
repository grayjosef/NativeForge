# Gate 166 — Data-Driven Source Authority / Factory Unlock

**Verifier:** `scripts/verify_nativeforge_source_authority.sh` → `RESULT=PASS`, `gate166_ready=true`
**Network requests during Gate 166: 0** (measured — every phase replaces `socket.socket` with one that raises and counts)
**Rows written: 0.** The live Gate 163 evidence is byte-identical.

---

## 1. What this gate removed

```python
# source_live_warrant_service.py — gone
AUTHORIZED_SOURCE_IDS: frozenset[str] = frozenset(
    {"nf-seed-2026-api-grants-gov-search2"}
)
```

Gate 163 was right to add it. Widening a frozenset is an edit somebody reviews,
and that is the correct ceremony for a first live request.

It was also **redundant**, which is the part that mattered. The authorization it
encoded already existed as accountable data before this gate touched anything:

| store | row | signed by |
|---|---|---|
| `nf_source_authorization_decisions` | `terms` approved | MAYHEM |
| `nf_source_authorization_decisions` | `human_review` approved | MAYHEM |
| `nf_source_authorization_decisions` | `live_fetch` approved | operator:MAYHEM |
| `nf_active_opportunity_sources` | activation signed, `disabled_at` NULL | MAYHEM |

Migration 0048's CHECK already makes an unsigned `approved` decision
**unwritable**. The constant restated a database guarantee in a place nobody
could audit, and at 1,000 sources it would have made every activation a code
change and a deploy.

## 2. The authority model (166A)

Existence and execution authority are different questions, and this gate
refuses to collapse them.

```text
unregistered   no catalog row
registered     a catalog row exists                      <- the 177 live here
reviewed       terms AND human_review approved + signed
activated      activation signed, not disabled
live_opted_in  live_fetch decision approved + signed
authorized     every operational fact also holds
retired        disabled_at is set                        <- beats the ladder
blocked        an explicit denial
review_required a terms guard demands a human
```

**`retired` is evaluated before the ladder and wins outright.** A disabled
source with four signed decisions is disabled; walking the rungs and taking the
highest would have reported it `live_opted_in`.

Governance complete is **not** a permitted request. Robots evidence,
attribution, collector capability and runtime readiness are conditions of the
moment, and the warrant still checks them on every request.

## 3. Proof that enforcement survived (166B)

A single positive case cannot distinguish enforcement from deletion — the real
source would still pass if the check had simply been removed. So every case is
a control:

| case | result |
|---|---|
| Grants.gov, unchanged data | **permitted**, state `live_opted_in` |
| **same id**, opt-in withdrawn | refused → `activated` |
| **same id**, decisions unsigned | refused → `registered` |
| **different id**, decisions complete | **authorized, no code edit** ← the unlock |
| `nf-seed-2026-fed-001` (a real catalog row) | refused → `registered` |
| no connection | refused — nothing derivable is nothing authorized |
| forged decision claiming permission | caught by the invariant |

The fifth row is the one worth reading twice: **presence in the seed CSV is not
authorization.** A real source id, a real host, and a refusal that names its
state.

## 4. Fleet facts, computed once (166E)

Gate 165 measured one authorization at ~332 ms and attributed it:

```text
_resolve_runtime -> build_runtime_readiness_facts   102 ms   no source_id
  build_scheduler_readiness                          51 ms   no source_id
  build_execution_health (x2)                        99 ms   no source_id
_resolve_collector -> measure_collector_capability   49 ms   source_id
```

**~70% was fleet-wide work invoked per source.** A 1,000-source sweep asked
whether the scheduler was ready a thousand times.

The hoist sits **below** the fact resolver, not beside it: Gate 162 pinned that
resolver's signature so no parameter could assert a fact, and its forbidden-word
list contains `fact` — a `fleet_facts` parameter was the wrong shape as well as
the wrong name. Instead, `fleet_fact_scope()` is an explicitly-scoped
`ContextVar`.

It is **not a cache**:

- **Explicit lifetime.** With no scope open, every call computes — byte-for-byte
  the pre-Gate-166 behaviour.
- **Immutable for the sweep.** A sweep that saw two answers to one fleet
  question produced a report true of no moment in time.
- **Not ambient.** `ContextVar`, not a module global. All 57 route modules are
  sync and run in anyio's **reused** worker threadpool, so `threading.local()`
  would leak one request's scope into the next.
- **Tenant-bound.** A scope opened for another organization is **bypassed and
  recomputed**, never answered from. A mismatch costs time, never correctness,
  and the bypass is counted so "the scope was silently useless" is visible.

`exercise=True` is never scoped: exercising writes and deletes fixture rows, and
reusing one exercise's result would report lanes exercised that were not.

## 5. Scale (166G)

Synthetic catalog entries only. Nothing written, nothing contacted.

| sources | sweep | per source | fleet computations | invariants |
|---|---|---|---|---|
| 10 | 143.6 ms | 14.36 ms | **2** | clean |
| 100 | 141.2 ms | 1.41 ms | **2** | clean |
| 1,000 | 138.2 ms | 0.138 ms | **2** | clean |
| 5,000 | **175.5 ms** | 0.035 ms | **2** | clean |

**Fleet computations are constant at every population** — measured as a count,
not inferred from a timing curve. **9,998 computations avoided at 5,000
sources.**

The real fleet: 180 registered (178 catalog + 2 reserved fixtures), 180
evaluated, 179 `registered`, 1 `live_opted_in`.

**UNKNOWN and not extrapolated:** fact-resolution cost at millions of payload
and attempt rows (the database holds 2 payloads and 1 attempt), concurrent
worker contention, any other database engine.

## 6. The leak this gate found (166I)

The genericity scan classifies by **AST node**, not by line text — a scan for
`grants.gov` finds the docstring explaining why a module must not depend on it.
Three buckets: documentation, adapter descriptor, leak.

It found a real one:

```python
# source_authorization_fact_resolver_service._resolve_attribution — before
from nativeforge.services.grants_gov_attribution_service import (
    MANIFEST_BLOCK_KEY, MANIFEST_NOTICE_KEY, build_attribution_contract,
)
```

`ATTRIBUTION_TEXT` there is the **verbatim Grants.gov notice, compared with
`==`**. So the generic resolver verified *every* source's recorded notice
against Grants.gov's string. Source #2 — its own publisher, its own terms, its
own required wording — would have had its correct notice rejected, and **no
amount of signing decisions could have fixed it.**

Nothing was wrong today, because there is one source. Everything would have been
wrong on the day this gate exists to enable.

The fix follows the pattern the capability layer already uses:
`ATTRIBUTION_CONTRACTS` keyed by `adapter_key` from the source's own catalog
row. Grants.gov's behaviour is unchanged — same module, same constant, same
character-for-character comparison.

**`generic_layer_leaks = 0`** across 15 modules. The 9 remaining hits are inside
adapter-keyed descriptor dicts, which is the architecture working.

## 7. The corpus stopped being authority (166D)

```python
if len(rows) != EXPECTED_ROW_COUNT:   # before — growth is a code edit
if len(rows) <  EXPECTED_ROW_COUNT:   # after  — shrinkage is refused
```

The property worth keeping — Sprint 257's corpus cannot silently be lost or
swapped — survives as a floor plus the existing by-id check on named additions.
Growth no longer requires editing a historical constant, because **a seed row
grants nothing**: it makes a source `registered`. Accountability moved to where
it belongs, and got stronger: four signed decisions rather than a number
somebody had to remember.

## 8. One runtime contract, no schema migration (166C / 166H)

`source_definition_service` projects one `SourceDefinition` over all three
stores. An adapter receives it and never learns which store answered which
field — so the stores can be consolidated later without touching an adapter.

**Nothing was migrated or deleted.** One runtime contract is needed before one
physical table is, and a risky migration performed for tidiness is how a
campaign loses a corpus. 35 fields classified, 0 unclassified.

The projection immediately surfaced a real disagreement in the live data:

```text
source_status = 'activation_pending'
activation_approved_by / _at = signed
```

The signed columns are authoritative and the label had drifted.
`source_status` is classified `DUPLICATED` and is **reported, never believed**.

## 9. Defects found in my own instruments

Three, each of which produced a confident wrong answer:

1. **`or -1` read a legitimate zero as missing** — `sweep_invariant_failures`
   failed all four synthetic scales, because a fleet with nothing authorized is
   the normal case. Absent and zero are different facts.
2. **Four early returns omitted `governance_complete`** — so
   `retired_source_reported_governance_complete` could never have fired. An
   unreachable refusal is unfalsifiable.
3. **The live-evidence pin named one row of two** — the robots preflight is also
   a live fetch. The pin failed honestly, but it was the instrument that was
   wrong, not the data.

A fourth, from Gate 165, is corrected in §10.

## 10. Two Gate 165 corrections

- **The "zero opportunity tables" measurement was taken against an empty file.**
  `sqlite3.connect("nativeforge.db")` **created** a 0-byte database; the real one
  is `nativeforge.local.db`. Re-measured against the real database: 48 tables,
  and three discovery tables exist — `nf_discovery_intake_candidates`,
  `nf_discovery_intake_runs`, `nf_discovery_review_items`, all **empty**. The
  conclusion stands (no canonical opportunity store holds records); the evidence
  offered for it did not.
- **The 5,000-source projection of 45,652 s was wrong**, then corrected to
  2,512 s in the Gate 165 report by applying registry growth only to the CSV
  component. This gate supersedes both: **175.5 ms**, because the dominant cost
  was never per-source work at all.

## 11. What Gate 166 deliberately did not do

No canonical opportunity table · no scheduler redesign · no replacement of the
evidence or replay machinery · no fourth source registry · no schema
consolidation · no second live source · no network request of any kind.
