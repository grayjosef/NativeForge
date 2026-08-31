# 675 — Gate 125: readiness delta

What creating `nf_award_requirements` moved, and the much longer list it did
not.

## Moved

```text
alembic head                                  0032      0033
award requirements table                      none      nf_award_requirements
                                                        32 cols, 19 CHECKs
award requirements repository                 none      7 operations
award_requirements schema_available           false     true
award_requirements repository_available       false     true
award_requirements write_path_available       false     true
award_requirements read_path_available        false     true
award_requirements_storage_available          absent    true
awarded_tracking_storage_available            absent    true
proof_audit_persistence_available             absent    false
capability lanes with schema                  3         4
capability lanes with a write path            3         4
capability lanes RLS-backed                   3         4
```

Both halves of awarded tracking now have storage. Gate 124 built the awards
half; this is the other one.

The guard also gained `write_award_requirement` in `LABEL_BOUND_OPERATIONS`, for
a reason specific to this table: a requirement carries no tenant label of its
own, so the only thing relating it to a tenant is the award's binding.

## Not moved

```text
customer_auth_live                          false
login_live                                  false
verified_operational_binding                false
customer_persistence_live                   false
capability lanes operational                0
ready_for_operational_awarded_tracking      false
operational_awarded_recommended             false
document_storage_live                       false
proof_audit_persistence_available           false
requirement_extraction_live                 false
ui_available                                false
beta_onboarding_ready                       false
production_rollout_ready                    false
production award requirements created       0
production proof records created            0
production awarded grants created           0
real customer rows written                  0
rows in nf_award_requirements               0
```

The spine's recommendation is unchanged: **customer authentication**. Every lane
lists it as a prerequisite, so no amount of schema moves any of them.

## The defect this gate surfaced in the spine

Gate 124 fixed `operational_awarded_recommended` to require both lanes. That was
right as far as it went and Gate 125 broke it again — twice, in one line.

**First**, the repaired conjunct was a silent no-op:

```python
awarded = by_name.get("awarded_grants_persistence", {})   # a *matrix row*
...
and not (awarded.get("unmet_prerequisites") or [])        # always True
```

`by_name` is built from the capability matrix, whose rows carry no prerequisites
at all. `None or []` is `[]`, `not []` is `True`, so the conjunct could never be
false for any lane, forever. A conjunct that cannot fail is the same defect as
an invariant that cannot fail: it reads as coverage.

**Second**, and the reason the conjunct was wanted: a lane's `operational` means
schema + anchor + RLS + repository + contract + auth. It says nothing about the
lane's *product* prerequisites, and this lane has one the spine has always
named:

```python
SPINE_PREREQUISITES["award_requirements_persistence"]
  = (customer_auth, awarded_grants_persistence, document_storage)
```

So with auth forged, both lanes reported `operational`, the recommendation went
true, and the invariant guarding it fired:

```text
awarded_recommended_operational_without_document_persistence
```

The invariant was right — evidence needs a home before anything claims to track
compliance. The derivation now reads the sequence entries, which carry
`unmet_prerequisites`, and reuses the `operational_out_of_sequence` flag each
entry already derives as exactly "operable, and not yet due".

```python
operational_awarded_recommended = bool(
    awarded_lanes[0].get("operational")
    and awarded_lanes[1].get("operational")
    and not any(lane.get("operational_out_of_sequence") for lane in awarded_lanes)
)
```

## Tests repaired because a lane genuinely moved

Ten tests failed on the focused regression, all of the same shape: Gate 114 and
Gate 124 used `award_requirements_persistence` as their stand-in for "a lane
with no table", and Gate 125 gave it one.

```text
test_gate114  operational_capabilities gained a lane
test_gate114  the "no table" list
test_gate114  the no-schema write test
test_gate114  the out-of-sequence report
test_gate114  requires_migrations
test_gate114  the demo fixture set and its two tests
test_gate114  two artifact assertions
test_gate124  "the award requirements lane is untouched by this gate"
```

Gate 124 hand-repointed two of these off `awarded_grants_persistence`. Doing
that again would have scheduled the same edit for Gate 126, so each is now
**derived from the capability model** instead:

```python
def _lanes_without_a_table() -> list[str]:
    matrix = build_capability_matrix(customer_auth_live=True)
    return [r["capability"] for r in matrix["rows"] if not r["schema_available"]]
```

The Gate 114 demo fixture's `missing_capability_schema` case — repointed once
already — now walks the capabilities and takes the first with no schema,
resolving today to `tenant_digest_persistence` / `write_digest_record`. It will
follow the empty lanes on its own from here.

Gate 124's `test_the_award_requirements_lane_is_untouched_by_this_gate` was
retired rather than repointed. Its claim was true of Gate 124 and this gate
deliberately made it false. What Gate 124 actually guaranteed, and what
survives, is the *separation*: an award and a requirement are different objects
in different tables, and building one does not build the other. That is what the
replacement asserts.

## The naturally occurring out-of-sequence lane is back

Gate 120 recorded that the natural instance of "operable, and not yet due" had
disappeared when identity binding was built, and forged one so the reporting
path stayed tested. Gate 125 brought a real one back:

```text
award_requirements_persistence
  operational              true (with auth forged)
  unmet_prerequisites      ['document_storage']
  operational_out_of_sequence  true
```

It has a table, a repository and an RLS policy, and lists a prerequisite that
does not exist. The test now asserts it appears without anything being forged,
alongside the forged case it already covered.

## Why the lane is still not operational

One reason, and it is the only one:

```text
no_customer_auth_so_nobody_owns_the_row
```

Schema, anchor, RLS policy, repository and contract are all present for this
lane. Auth is what is left.

## What operational tracking still needs

```text
operational_component_missing:customer_persistence_live
operational_component_missing:document_storage_live
operational_component_missing:requirement_extraction_live
operational_component_missing:ui_available
operational_component_missing:verified_operational_identity_binding
```

Plus one this gate added as a measured fact rather than a component:
`proof_audit_persistence_available` is false, and an invariant refuses a
readiness result claiming operational tracking without it.

`award_requirements_storage_available` and `awarded_grants_storage_available`
are reported per lane rather than rolled into one flag. A reader who sees one
true and one false learns something a single flag would hide, and
`awarded_tracking_storage_available` — both lanes — is stated separately again,
with an invariant refusing it unless both hold.

## The sentence to refuse

> NativeForge tracks your reporting deadlines.

It does not. Two tables exist, two repositories address them, and every
production write is refused because nobody can be authenticated as the tenant a
requirement would bind to.

A deadline is the half somebody is actually held to. The promise that a missed
one will be caught needs a running system with a real award in it, a document
store the proof can live in, and an audit trail that records who filed what and
when. This gate built one of those four.

## The three boundaries preserved

```text
projected burden   what a NOFO suggests will be required if you win
active obligation  what this award requires, now
unsupported        what a document nobody could read appeared to say
```

All three derive from `requirement_source`; none is an input; five CHECK
constraints refuse the contradictions.

```text
fixture cases                                14
fixture cases recording a projection          1
fixture cases that became an obligation       0
fixture cases a calendar could count down to  9
```

## An estimate is not a deadline

`DATE_CALCULABLE_STATUSES` is `verified` and `calculated`. An estimated date is
stored, shown as estimated, flagged for a human, and never counted down to —
and neither is a date claimed by a document nobody could read.

That second one nearly shipped broken: `date_is_calculable` was computed before
the unsupported downgrade, so an unreadable document reported a countdown-ready
deadline. Fixed by ordering, guarded by three invariants.

## What Gate 125 deliberately did not build

**The proof audit trail.** `PROOF_ACTIONS` has six verbs and `build_audit_trail`
returns a sequence, so one requirement submitted, rejected, resubmitted and
accepted is four rows with four actors and four timestamps. Putting that on the
requirement row would mean overwriting the history, which is the one thing an
audit trail may never do. `proof_audit_persistence_available` is measured by
import, so it moves on its own the day the table exists.

**The document store.** `award_document_store_service` does not exist. Doc 598
listed it as next action 4 in August and it still is. `proof_document_ref` holds
a reference that resolves to nothing, and a reference supplied without a store
is refused by name.

**An API route.** Ten route decorators exist and none serves an award. Three
reasons, the third specific to this gate:

```text
1  a read route needs a session to scope by, and /current-user 401s for
   everybody, so the authenticated branch is unreachable and untestable
2  the table holds zero rows, so the route's only behaviour is
   `no_requirements`
3  a requirement is a deadline somebody is held to. The first surface that
   serves one is the surface that will be believed when it says nothing is
   due, and an empty table returning `no_requirements` is indistinguishable
   from a tenant with no obligations. That distinction is the entire product
```
