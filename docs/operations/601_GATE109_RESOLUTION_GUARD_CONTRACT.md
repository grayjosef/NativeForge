# 601 — Gate 109C: resolution guard contract

`src/nativeforge/services/tenant_customer_org_resolution_guard_service.py`

The checkpoint between a product-lane label and a security boundary.

## Why a guard is needed at all

Gate 109A found that the isolation which actually exists is org-scoped: Postgres
RLS keys on `app.current_org_id`, and `tenant_id` has no column and no
enforcement anywhere in the tree.

Every tenant-scoped surface built since Gate 103 will eventually read or write
org-scoped storage. The moment it does, something has to decide whether the pair
in hand is safe to join. That decision is this service, and it exists before
persistence precisely so there is no window in which the join happens unguarded.

## Deny by default, per operation

Permission is derived affirmatively from the binding status. There is no
permissive default to subtract from, and no caller-supplied flag appears in the
decision:

```text
verified_binding   operational reads and writes
demo_fixture       demo reads and writes only
pending_review     inspection only; writes blocked
unbound            operational reads and writes blocked
conflict           everything blocked
revoked            everything blocked
unknown            everything blocked
```

Nine operations are covered — read and write for tenant digest, awarded grants,
document library and source watchlist, plus beta onboarding. An unrecognised
operation resolves to `unknown` and is refused.

## Unbound and conflict and revoked block reads and writes

An unbound pair means nobody has asserted a relationship. There is nothing to
read *from* and nothing to write *to*, and pretending otherwise is how a query
ends up scoped to the wrong organization.

Conflict and revoked block everything outright: one is a pair that cannot be
right, the other a pair that was withdrawn.

## pending_review permits inspection but never a write

The asymmetry is deliberate. Pending means somebody asserted a relationship and
it has not been checked — and inspection is how it gets checked. Blocking reads
would make a pending binding unverifiable, which would make the status useless.

Blocking writes is not negotiable: an unverified pair must never be the thing a
record is filed against.

## demo_fixture is not a lesser production

A demo binding does not grant a weaker version of operational access. It grants
demo operations and nothing else. Used outside a demo context it is refused with
`demo_binding_cannot_reach_an_operational_surface`.

The tempting shortcut — "let the demo binding through, it is only a read" — is
exactly how a demo tenant ends up reading a real organization's awarded grants.

A verified binding used *in* a demo context is refused too, and named. Running
real credentials through a demo surface is a mistake worth catching rather than
quietly allowing.

## cross_tenant_risk is reported on the attempt

True whenever an operational operation is attempted without a verified binding,
or whenever the binding is in conflict or revoked — **even when the operation is
refused**. The useful signal is that somebody tried, not merely that it failed.

Risk always routes to `human_review_required`, and an invariant fails a result
carrying risk without it. Another re-derives the risk from the measurements and
fails a tampered value.

## Invariants, and the mutations they catch

```text
blocking status permitted access          conflict / revoked let something through
unbound binding permitted access
pending review permitted a write
demo binding permitted operational access
write permitted without a verified binding
cross tenant risk disagrees with the measurements
cross tenant risk without human review
resolution refused without a reason
```

Every one was verified by introducing the corresponding defect and confirming a
test fails. The permission paths are tested too — a verified binding really does
allow operational reads and writes, and a demo binding really does work in a demo
context — because a guard that refuses everything proves nothing.

## The guard joins nothing

```text
records_joined       false
persisted            false
live_fetch_performed false
```

It decides whether a join is permitted. It does not perform one, and it reaches
no storage.
