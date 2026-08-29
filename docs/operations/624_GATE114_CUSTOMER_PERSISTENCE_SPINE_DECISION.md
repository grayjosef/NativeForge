# 624 — Gate 114D: the customer persistence spine decision

`src/nativeforge/services/customer_persistence_spine_decision_service.py`

The order the eight lanes should become real, and what each is waiting on.

## Order is a safety question

Each lane, built out of order, produces a specific dishonest artifact:

```text
digest before auth + persistence + sources   a digest of nothing, delivered to
                                             nobody, about sources nobody watches
awarded before document persistence          an award record whose evidence has
                                             nowhere to live, so its requirements
                                             cannot be substantiated
onboarding before auth + binding + profile   an onboarding flow collecting a
                                             Tribe's details into no owned row
```

Those are the three constraints the brief names. They are enforced as invariant
failures with reasons, not as advice in a document — including this one.

## The sequence

```text
1. identity_binding_persistence     waiting on: customer_auth
2. tenant_profile_persistence       waiting on: customer_auth, identity_binding
3. awarded_grants_persistence       waiting on: customer_auth, tenant_profile
4. award_requirements_persistence   waiting on: customer_auth, awarded_grants,
                                                document_storage
5. document_library_persistence     waiting on: customer_auth, document_storage
6. tenant_digest_persistence        waiting on: customer_auth, tenant_profile,
                                                live_source_collection
7. source_watchlist_persistence     waiting on: customer_auth,
                                                live_source_collection
8. beta_onboarding_persistence      waiting on: customer_auth, identity_binding,
                                                tenant_profile
```

Position is not preference. `ready_to_build_next` is derived by walking the
dependency graph and taking the first lane whose prerequisites are all met, so
the recommendation moves when the world does. A test forces `customer_auth`
true and asserts the sequence advances — otherwise this is a list, not a
decision.

## Why identity binding is first

Nothing can be owned by an organization until something says which organization
a tenant label corresponds to. Every lane below it inherits that answer.

## The next gate is not the next lane

```text
ready_to_build_next:       none
next_gate_recommendation:  customer_authentication
```

Every lane in the spine lists `customer_auth` as a prerequisite. No amount of
schema moves any of them, and auth is the only thing that unblocks more than one
at once. Six of the eight lanes also need a migration, and building those first
would produce six tables nobody can write to.

## A disagreement the decision reports rather than hides

The capability model and the spine answer different questions:

```text
capability model   can this be written?
spine              should it be yet?
```

They can disagree. With auth forced live, `tenant_profile_persistence` becomes
mechanically operational while its spine prerequisite — identity binding
persistence — is still unmet.

An earlier version of this service treated that as an invariant failure. That
was wrong: it is a real state, and the spine exists precisely to notice it. The
decision now reports it as `capabilities_operational_out_of_sequence` with a
matching blocked reason, and an invariant fires if a premature lane is *not*
reported. Suppressing the disagreement would have been the more dangerous
artifact.

## What this service will not do

It recommends building, never operating. Every lane it names still passes
through the Gate 114C guard for each individual write, and every capability
still needs customer auth before any of it operates.

```text
operational_digest_recommended      false
operational_awarded_recommended     false
beta_onboarding_recommended         false
customer_persistence_live           false
schema_changed                      false
rows_written                        0
```

Demo persistence is allowed, and only under the label `demo_fixture`. An
invariant fails any decision that permits demo persistence without it.
