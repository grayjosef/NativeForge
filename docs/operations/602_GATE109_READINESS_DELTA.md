# 602 — Gate 109D/E/F: readiness delta

## What changed

An identity binding is now a prerequisite for operational readiness on every
tenant-scoped surface. Three readiness services gained the same component, each
detected rather than declared:

```text
awarded grants readiness   verified_operational_identity_binding
tenant digest readiness    verified_operational_identity_binding
tenant beta readiness      verified_operational_identity_binding
```

All three report it `False`, so all three operational answers stay `False` and
now name the identity gap among their blocked reasons.

## Awarded grants

```text
ready_for_demo_contract                 true   unchanged
ready_for_operational_awarded_tracking  false  now also blocked on the binding
```

`awarded_grant_record_service` previously recorded
`tenant_org_binding_status` from a two-value vocabulary, `{caller_supplied,
unknown}`. Gate 109 found that too weak: two strings arriving together is not a
statement that they belong to each other. It now imports the binding statuses and
builds a real binding record.

```text
both ids, no verification  ->  pending_review
one id missing             ->  unbound
identical ids              ->  conflict
demo, labelled             ->  demo_fixture
```

Two Gate 108 tests that pinned the old vocabulary were updated rather than
deleted — the distinction they guarded is now finer, not gone.

An awarded record additionally carries the whole binding record and
`operational_identity_binding_verified`. Invariants fail a record whose status
disagrees with its own binding record, and one claiming verification it does not
have.

## Tenant digest

```text
ready_for_demo_preview       true   unchanged
ready_for_operational_digest false  now also blocked on the binding
```

A digest is tenant-scoped; row-level security keys on the organization.
Delivering one to a real Tribe means joining those two identity spaces, and
without a verified binding that join is a guess.

## Beta onboarding

```text
ready_for_demo             true   unchanged
ready_for_beta_onboarding  false  now also blocked on the binding
customer_auth_live         false
customer_persistence_live  false
```

Onboarding a real Tribe means binding their tenant to their customer
organization. Without that, every tenant-scoped surface would be reaching into
org-scoped storage on an assumption.

## Demo fixtures

`tenant_customer_org_demo_identity_fixture_service` provides five labelled
bindings, one per status the guard must handle: demo, unbound, pending_review,
conflict, revoked.

```text
production_verified_bindings   0
real_customer_data             false
real_tenant_records_created    false
real_customer_records_created  false
```

Every identifier is invented and prefixed `nf-demo-`. No demo binding is
production verification, no tenant record is created from a customer org, and no
customer record is created from a demo tenant.

The fixture builds the guard matrix in both contexts. In the operational
context, **zero writes are permitted** across all five bindings and all nine
operations; the only permitted rows are the `pending_review` binding's inspection
reads, which are allowed by design.

### An invariant that fired on correct behaviour

The first draft of the fixture's operational check failed on *any* allowed row,
which caught the `pending_review` inspection reads. Those are correct. An
invariant that fires on correct behaviour teaches people to ignore it, so the
check was narrowed to demo bindings specifically — which is what its name always
claimed — and a separate check added for writes across all statuses.

## What remains false

```text
verified operational binding   false
operational awarded tracking   false
operational digest             false
beta onboarding                false
customer auth                  false
customer persistence           false
document storage               false
live source collection         false
source monitoring              false
source coverage                false
production rollout             false
controlled customer pilot      false
```

No live fetch occurred. No collector ran, no URL was requested, no scraper was
activated, and nothing was persisted.

## What this gate deliberately did not do

```text
reconcile org_id and organization_id   ~70 services and ~18 tables use these;
                                       its own gate, and larger than this one
persist bindings                       no storage is live
rewrite Gate 51's derivation           classified as evidence, left in place
touch RLS                              the org-scoped boundary is the one that
                                       works, and this gate does not disturb it
```

## Next

A verified binding needs somewhere to live and someone to verify it. That means
a binding store and an admin path — which is persistence work, and is now
unblocked by having the contract it must satisfy.
