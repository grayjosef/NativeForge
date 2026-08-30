# 666 — Gate 123C: tenant profile validation

`src/nativeforge/services/tenant_profile_persistence_validation_service.py`

## Eleven checks, and none of them fills a gap

```text
recognition_status_known             established AND actionable
operating_states_valid               a list of two-letter codes, actionable
service_area_present                 reported, never used to decide
applicant_classes_present            recognised, not "unknown", actionable
priority_topics_present              at least one, or ranking is unweighted
excluded_topics_valid                no topic both wanted and excluded
digest_frequency_valid               weekly, daily or none
routing_rules_valid                  a recognised audience, or alerts reach
                                     nobody
source_watchlist_preferences_valid   at least one source declared
unknowns_labelled                    every unknown was named, not defaulted
human_review_required                any unknown, or any blocked reason
```

A field that was not supplied stays unknown. A validation that could not run
says so rather than defaulting to pass.

## The four refusals, bridged rather than restated

Imported from `tenant_beta_profile_service`. Two copies of a refusal is how one
of them quietly stops being enforced, and a test asserts the bridged set equals
the declared one.

```text
recognition_status_from_name_or_state
federal_eligibility_from_state_recognition
operating_state_from_mailing_address
applicant_class_from_tenant_kind
```

Each is a legal distinction, not a modelling preference. South Carolina
recognising a Tribe says nothing about federal programme eligibility, and the
inverse is equally false.

## operating_states decides; service_area describes

```text
state_source_matching_enabled = operating_states_valid
```

One assignment, and an invariant that fires if the two ever diverge — if
`state_source_matching_enabled` ever picks up a second source, that invariant is
what notices.

`matches_state_source` reports which rule decided:

```text
decided_by                    operating_states
mailing_address_considered    false
service_area_considered       false
```

Three fields to answer one question, because "did it match" is less useful than
"what decided". A profile whose service area reads *Columbia, South Carolina*
and whose `operating_states` is empty matches no SC source, and the result says
`state_source_matching_disabled_for_this_profile` rather than simply `false`.

## demo_fixture is not actionable, on purpose

```text
ACTIONABLE_FACT_STATUSES = {verified, tenant_supplied}
```

`demo_fixture` is excluded. A demo value must never drive a real decision — Gate
103's rule, and the reason the status vocabulary exists at all.

The consequence is worth stating: **every profile in the Gate 123 fixture file
is storable and none is actionable.** A fixture that reached
`profile_ready_for_matching` would have proved the fixture path and quietly
broken the rule.

## A two-letter code, or it is not a state

```text
_STATE_CODE_RE = ^[A-Z]{2}$
```

Anything longer is a description somebody hoped would be parsed. `South
Carolina` is refused as an operating state and named in the reason; `SC` is
accepted.

Combined with the repository refusing a delimited string, there is no path from
prose to a state code.

## A contradiction is escalated, not resolved

A topic that appears in both `priority_topics` and `excluded_topics` blocks
validation and names the topic. Guessing which one wins would be inventing a
preference, and the tenant is the only one who can settle it.

## profile_ready_for_matching is reachable

Six conjuncts, all required, and a test drives them all true with zero blocked
reasons — so every refusal above is falsifiable rather than a constant. The
seven gates before it each shipped an unreachable branch once; this one was
built reachable.
