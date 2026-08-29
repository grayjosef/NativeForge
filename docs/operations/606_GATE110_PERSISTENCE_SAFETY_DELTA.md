# 606 — Gate 110D/E: persistence safety delta

`src/nativeforge/services/identity_persistence_safety_guard_service.py`

## Two guards, two questions

```text
Gate 109 resolution guard   may these two records be joined?
Gate 110 persistence guard  may a row be written under this identifier?
```

Different failure modes. A bad join shows somebody the wrong data. A bad write
puts a Tribe's compliance record in a row the database cannot protect, where it
sits until an audit finds it.

## The rule

A write is permitted only under an identifier row-level security can enforce,
and only once any label has resolved to one.

```text
organization_id   UUID     may persist
org_id            UUID     may persist - alias of the authority
org_id            string   blocked - a label wearing the name
customer_org_id   any      blocked without resolving to the authority
tenant_id         any      blocked, always
demo values       any      blocked, always
```

Across the committed safety matrix — six identities against six persist
operations — `write_allowed` is true for `organization_id` and a UUID-shaped
`org_id`, and for nothing else. `tenant_id_writes_allowed` is 0.

## tenant_id alone cannot persist operational customer data

Every one of the six persist operations refuses it, and each refusal is tested
individually rather than in aggregate.

## A verified binding does not change that

The subtlest rule in the gate, and the one most likely to be shortcut later.

```text
tenant_id + verified binding  ->  still blocked
```

The binding says which organization the tenant corresponds to. The write must
then use **that organization's id**. Writing under the label with the binding
merely on file would leave a row RLS cannot see — the binding would be correct
and the row still invisible to the boundary.

`customer_org_id` with a verified binding is refused for the same reason:
`rls_compatible` stays false because the value is not the authority.

## Any ambiguity blocks

Derived affirmatively: the role contract must permit persistence, the value must
be UUID-shaped, the value must be non-demo, and no binding requirement may be
outstanding. An unrecognised operation blocks. An absent value blocks.

## Defence in depth, made observable

The guard re-checks shape and the binding requirement even though the role
contract already implies both. Those conjuncts are unreachable while the contract
is self-consistent — which means a mutation removing either survives against real
inputs, and did on the first mutation run.

Three tests forge an inconsistent role and confirm each conjunct holds on its
own, including the narrowest case: RLS-compatible, binding required, binding
present, no blocked reasons — where `not binding_required` is the only thing left
standing.

An invariant that cannot be observed is not protection; it is decoration.

## Readiness

Gate 109 already made operational readiness false on all three surfaces via
`verified_operational_identity_binding`, and it remains false. Gate 110 added no
duplicate key — a second flag false for the same reason would be noise, not
safety.

What changed is the awarded readiness next-action, which now names the decided
store so the trail from binding contract to store decision is coherent.

```text
operational awarded tracking   false
operational digest             false
beta onboarding                false
customer auth                  false
customer persistence           false
document storage               false
live source collection         false
source monitoring              false
source coverage                false
```

Demo contracts remain available on all three surfaces, and the verified binding
contract from Gate 109 remains available.

## The guard writes nothing

```text
rows_written           0
persisted              false
live_fetch_performed   false
```

It decides whether a write is permitted. It performs none, and reaches no
storage. No live fetch occurred in this gate, no collector ran, and no scraper
was activated.
