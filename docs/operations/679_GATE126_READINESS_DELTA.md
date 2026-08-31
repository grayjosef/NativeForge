# 679 — Gate 126: readiness delta

What creating `nf_award_requirement_proof_events` moved, and the much longer
list it did not.

## Moved

```text
alembic head                              0033      0034
proof events table                        none      nf_award_requirement_proof_events
                                                    26 cols, 16 CHECKs
proof audit repository                    none      8 operations
proof_audit_persistence_available         false     true
proof_audit_schema_available              absent    true
proof_audit_repository_available          absent    true
proof_audit_write_path_available          absent    true
proof_audit_storage_available             absent    true
capability lanes                          8         9
capability lanes with schema              4         5
capability lanes with a write path        4         5
capability lanes RLS-backed               4         5
spine sequence entries                    8         9
guard operations                          9        10
```

All three post-award lanes now have storage: an award, what it obliges, and what
was filed against it.

The guard gained `write_proof_event` in `LABEL_BOUND_OPERATIONS`. A proof event
inherits its tenant through two hops — requirement, then award — so the binding
is the only thing relating it to anybody.

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
requirement_extraction_live                 false
ui_available                                false
beta_onboarding_ready                       false
production_rollout_ready                    false
production proof records created            0
production award requirements created       0
production awarded grants created           0
real customer rows written                  0
rows deleted                                0
rows in nf_award_requirement_proof_events   0
```

The spine's recommendation is unchanged: **customer authentication**. Every lane
lists it as a prerequisite.

## The defect I planted last gate

Gate 125 added a measured probe so proof/audit persistence would move on its own
the day it was built:

```python
def _proof_audit_persistence_available() -> bool:
    return _module_importable(
        "nativeforge.services.award_requirement_proof_repository_service"
    )
```

Gate 126C asks for `award_requirement_proof_audit_repository_service`.

```text
probe expected   ..._proof_repository_service
gate 126 built   ..._proof_audit_repository_service
same name?       NO
```

Building at the name the brief specifies would have left
`proof_audit_persistence_available` **false forever**, with the readiness report
insisting the store did not exist while it sat in the same directory. Exactly
the family Gate 124A found — `awarded_grant_record_contract_service` against
`awarded_grant_record_service` — a detector reporting on a *name* rather than a
capability.

Gate 124 added a test asserting every module in `CAPABILITY_CONTRACT_MODULES`
imports, so a third typo could not hide there. `CAPABILITY_REPOSITORY_MODULES`
had no such test, and that is the hole this came through.

**Repaired three ways.** Readiness stops naming a module and asks the capability
model. `CAPABILITY_REPOSITORY_MODULES` is now the single place a repository
module is named. And `test_every_mapped_repository_module_imports` closes the
hole, alongside a readiness invariant refusing the measured flag and the lane's
own storage to disagree.

## The two stale claims Gate 125 was left telling

Both are also mine, from last gate, and both would have gone stale *silently*.

**In three files**, Gate 125 froze `proof_audit_persistence_available: False` —
in its artifact `FIXED_CLAIMS`, in its fixture-set constants, and in its
validation results. Gate 126 falsified all three.

The dangerous shape is the first: the artifact's own invariant compared the
declaration against the same frozen constant, so the two agreed with each other
while both disagreed with reality. A check that agrees with itself is worse than
no check.

```text
before  FIXED_CLAIMS says false, invariant compares against FIXED_CLAIMS, pass
after   declaration measures readiness, scan compares against readiness
```

The fixture set and the validation service simply stopped claiming it. A fixture
set states what it did; a validation result states what it concluded about the
event in front of it. The state of a neighbouring lane is readiness's question,
and answering it in three places made all three wrong at once.

The artifact capability scan now measures:

```python
if key in measured and bool(value) is not measured[key]:
    found.add(f"capability_claim_disagrees_with_reality:{key}")
```

which refuses *denying* an available capability as well as claiming an
unavailable one. A claim becomes acceptable the day it becomes true rather than
the day somebody remembers to edit the file.

## A ninth capability lane

A proof event is customer data, owned by an organization, RLS-scoped, with its
own table and repository. That is what a persistence lane is, so modelling it as
a bare readiness boolean would have hidden a real lane behind a flag — the
inverse of the defect above.

Measured cost before deciding: exactly one position assertion
(`beta_onboarding_persistence position == 8`), which was reaching for
"onboarding is last" and should have been derived anyway.

Position in the sequence, and why:

```text
4. award_requirements_persistence   what the award obliges
5. proof_audit_persistence          a requirement without its proof trail
                                    records what was due and not what was
                                    done, and an auditor asks the second
6. document_library_persistence     evidence needs a home
```

Its prerequisites are `(customer_auth, award_requirements_persistence,
document_storage)`. Document storage is false, so with auth forged the lane is
`operational_out_of_sequence` — operable, and not yet due — exactly as
award_requirements has been since Gate 125.

## Awarded tracking is three lanes now

Gate 124 made `operational_awarded_recommended` require two lanes. Gate 125
added the unmet-prerequisite conjunct. Gate 126 makes it three:

```python
operational_awarded_recommended = bool(
    all(lane.get("operational") for lane in awarded_lanes)
    and not any(lane.get("operational_out_of_sequence") for lane in awarded_lanes)
)
```

An auditor reads all three — the award, what it obliged, what was filed — so
recommending operation on two would recommend a compliance record with no
evidence in it.

## Why the lane is still not operational

One reason, and it is the only one:

```text
no_customer_auth_so_nobody_owns_the_row
```

## What operational tracking still needs

```text
operational_component_missing:customer_persistence_live
operational_component_missing:document_storage_live
operational_component_missing:requirement_extraction_live
operational_component_missing:ui_available
operational_component_missing:verified_operational_identity_binding
```

## The sentence to refuse

> NativeForge keeps your compliance evidence.

It does not. Three tables exist and every production write is refused because
nobody can be authenticated as the tenant a filing would bind to.
`proof_document_ref` names a document and there is no store behind it, so the
evidence itself is still wherever the Tribe put it.

What this gate built is the record of *what happened to* evidence — filed,
accepted, rejected, superseded — not the evidence.

## What is retained, and why that is the point

```text
rejected    the proof reference stays on the row
superseded  the prior event stays, and the new one points back
archived    the row stays and leaves the active view
deleted     nothing. There is no delete path
```

A rejection that erased what was filed would make "we rejected it"
indistinguishable from "nothing was ever filed". A supersession that replaced
the prior row would erase what was believed before the correction. Both are
opposite facts about the same Tribe, and both are what a funder's auditor asks
about.

```text
fixture cases                    14
fixture cases removing a record   0
production proof records          0
```

## What Gate 126 deliberately did not build

**The document store.** `award_document_store_service` still does not exist and
is now the prerequisite blocking two lanes rather than one. Doc 598 listed it as
next action 4 in August.

**An API route.** No route decorator matches awards, requirements or proof.
Three reasons, the third specific to this gate:

```text
1  a read route needs a session to scope by, and /current-user 401s for
   everybody, so the authenticated branch is unreachable and untestable
2  the table holds zero rows, so the route's only behaviour is
   `no_proof_events`
3  a proof event is the record a funder's auditor reads. The first surface
   that serves one is the surface that will be believed about whether a Tribe
   filed something, and an empty table returning `no_proof_events` is
   indistinguishable from a Tribe that filed nothing. Serving that before a
   real tenant can be authenticated builds the failure mode first
```
