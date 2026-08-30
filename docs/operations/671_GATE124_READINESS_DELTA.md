# 671 — Gate 124: readiness delta

What creating `nf_awarded_grants` moved, and the much longer list it did not.

## Moved

```text
alembic head                              0031      0032
awarded grants table                      none      nf_awarded_grants, 8 CHECKs
awarded grants repository                 none      6 operations
awarded grants schema_available           false     true
awarded grants repository_available       false     true
awarded grants write_path_available       false     true
awarded grants read_path_available        false     true
awarded_grants_storage_available          absent    true
capability lanes with schema              2         3
capability lanes with a write path        2         3
capability lanes RLS-backed               2         3
```

Two lane mappings were also corrected. Gate 124A found five of eight capability
lanes pointing at contract modules that do not exist, and two of the five were
one token away from a real service:

```text
mapped   awarded_grant_record_contract_service -> awarded_grant_record_service
mapped   award_requirements_model_service      -> award_requirement_model_service
```

Both lanes had been reporting `no_service_decides_what_may_be_written` while a
432-line and a 494-line service decided exactly that. The other three absences
are genuine and stay false. A test now asserts which mapped modules import, so a
third typo cannot hide as a false negative.

## Not moved

```text
customer_auth_live                          false
login_live                                  false
verified_operational_binding                false
customer_persistence_live                   false
capability lanes operational                0
ready_for_operational_awarded_tracking      false
award_requirements_persistence              every field unchanged
document_storage_live                       false
requirement_extraction_live                 false
ui_available                                false
beta_onboarding_ready                       false
production_rollout_ready                    false
production awarded grants created           0
production award requirements created       0
real customer rows written                  0
rows in nf_awarded_grants                   0
```

The spine's recommendation is unchanged: **customer authentication**. Every lane
lists it as a prerequisite, so no amount of schema moves any of them.

## The second defect this gate surfaced

`operational_awarded_recommended` in the spine decision was derived from one
lane:

```python
operational_awarded_recommended = bool(awarded.get("operational"))
```

while the invariant guarding it has always asked about a different one:

```python
awarded = by_name.get("award_requirements_persistence", {})
if decision["operational_awarded_recommended"] and "document_storage" in (
    awarded["unmet_prerequisites"]
):
    fails.append("awarded_recommended_operational_without_document_persistence")
```

It never mattered while both lanes were equally empty. Gate 124 built the awards
half and deliberately left the requirements half for a later gate, which
separated them for the first time — and with auth forged, the derivation said
"recommend operational awarded tracking" while the invariant said document
storage is missing.

The invariant was right. "Awarded tracking" is two lanes: an award is a row, and
tracking is the requirements hanging off it with their own due dates and their
own proof trail. The derivation now requires both:

```python
operational_awarded_recommended = bool(
    awarded.get("operational") and awarded_requirements.get("operational")
)
```

Same family as the rest: a field named for a capability reading only part of
what that capability is.

## Tests updated because a lane genuinely moved

```text
test_gate114  operational_capabilities gains awarded_grants_persistence
test_gate114  awarded grants leaves "a lane with no table"
test_gate114  the no-schema write test repoints to award requirements
test_gate114  ready_to_build_next moves on again
test_gate114  awarded grants leaves requires_migrations
test_gate120  the "only that lane" test now derives instead of hard-coding
```

The Gate 114 demo fixture set's `missing_capability_schema` case moved from
awarded grants to award requirements for the same reason: it needs a lane with
genuinely nowhere to write, and awarded grants is no longer one.

Gate 120's `test_the_repository_moves_the_binding_lane_and_only_that_lane`
listed the lanes expected to be false, which made it a record of which
repositories existed in August rather than a check that the detector agrees with
reality. It now derives: a lane may report a repository exactly when one is
reachable. That catches the Gate 120 defect in both directions and needs no
editing next gate.

## Why the lane is still not operational

One reason, and it is the only one:

```text
no_customer_auth_so_nobody_owns_the_row
```

Schema, anchor, RLS policy, repository and contract are all now present for this
lane. Auth is what is left.

## What operational tracking still needs

```text
operational_component_missing:customer_persistence_live
operational_component_missing:document_storage_live
operational_component_missing:requirement_extraction_live
operational_component_missing:ui_available
operational_component_missing:verified_operational_identity_binding
```

`awarded_grants_storage_available` is reported separately from
`customer_persistence_live` rather than folded into it. Both answers are
load-bearing: "built" says what this gate did, "live" says what a Tribe can do.
An invariant refuses a readiness result where persistence is live without
storage, so the first can never be read as the second.

## The sentence to refuse

> NativeForge tracks your awarded grants.

It does not. A table exists, a repository addresses it, and every production
write is refused because nobody can be authenticated as the tenant an award
would bind to.

An award is a real obligation to a real funder. The gap between storing one and
tracking one is a promise that a missed deadline will be caught, and nothing in
this gate makes that promise.

## The separation preserved

```text
projected burden   what a NOFO suggests will be required if you win
active obligation  what this award requires, now
```

`active_obligation_status` is its own column, derived from this award's own
extraction status and never from anything on the pursuit side.
`prepare_award_write` has no parameter that could carry a projection.

```text
fixture cases                            11
fixture cases establishing an obligation  0
```

## What Gate 124 deliberately did not build

**Award requirements.** They get their own table in a later gate, because a
requirement recurs — quarterly financial reports, annual performance reports —
so one award produces dozens of rows with their own due dates and proof trails.
A single table would mean repeating the award on every requirement row or
storing a JSON array nothing can query by due date, and a calendar that cannot
query by due date is not a calendar.

**An API route.** Three reasons, the third specific to this gate:

```text
1  a read route needs a session to scope by, and /current-user 401s for
   everybody, so the authenticated branch is unreachable and untestable
2  the table holds zero rows, so the route's only behaviour is `no_awards`
3  an awarded grant is the most consequential object in this product - a real
   obligation to a real funder - and the first surface that serves one should
   be built when a real tenant can be authenticated to read it, not eight
   gates earlier against an empty table
```
