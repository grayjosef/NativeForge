# 574 — Gate 103D: tenant source priority contract

`src/nativeforge/services/tenant_source_priority_service.py`

Connects a tenant profile to SC and federal source priority. It activates
nothing, monitors nothing, and fetches nothing.

## What the registry actually holds

```text
fixtures/external_source_registry/nativeforge-source-registry-v2.csv
  381 rows total
  303 federal
   57 state - every one of them SC
   21 private
```

All 57 state rows are South Carolina. That is why "SC first" rests on real
registry coverage rather than an aspiration, and it is also why the SC tier is
worth having: it is the entire state-scoped surface of the registry.

## Five tiers, strongest first

```text
tenant_state_priority   the tenant's own operating state
federal_priority        303 rows
other_state             a state the tenant does not operate in
private                 out of beta scope unless asked for
out_of_scope
```

## Priority is an ordering, not an activation

Ranking a source first says which one a collector would reach for **if one were
running**. Gate 93 found all five Phase 1 collectors `not_active` and Gates
98–102 kept them that way.

```text
sources_active     0
sources_monitored  0
live_coverage      false
collectors_activated 0
```

All derived from the rows, all held by invariants, and every row carries
`active: false`, `monitored: false`, `fetch_performed: false` of its own. A
ranked list of 360 in-scope sources with zero active collectors is exactly the
state of this repository, and the numbers say so rather than the ordering
implying otherwise.

`no_active_collectors` is always in `blocked_reasons`, and an invariant fails a
ranking that omits it.

## Priority is tenant-specific

```text
tenant operating in SC   57 SC sources ranked first, then 303 federal
tenant operating in NC    0 SC sources, 303 federal
tenant with no state      0 SC sources, 303 federal
```

An invariant fails any result claiming an SC tier without SC in the tenant's
operating states, and another fails a non-zero SC count for a non-SC tenant.
This mirrors Gate 103B, where `sc_priority` is derived from the tenant's own
states.

## Source status is carried through, never upgraded

Each row keeps the activation status the registry gives it:

```text
not_active               nothing runs
human_review_only        a person must look first
terms_review_required    terms have not been read
activation_allowed       cleared - and still not running
```

Ranking never changes a status, and an invariant fails any row that is both
`activation_allowed` and `active` — only a collector could make it active, and
there is none.

`requires_login` is read tri-state. Gate 92 found a seed reading that column as
a raw string and getting 22 rows wrong, so an unrecognised value here means
`terms_review_required` rather than a permissive default.

## Ordering is stable

Rows sort by tier then source id — no clock, no dependence on input order — so
the committed artifacts regenerate byte-identically.

## Read from the fixture, never from the network

The registry CSV is a file read. The service imports no HTTP client and an AST
test proves it.
