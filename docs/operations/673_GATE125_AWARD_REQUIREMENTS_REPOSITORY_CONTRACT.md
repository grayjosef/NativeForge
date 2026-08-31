# 673 — Gate 125: the award requirements repository contract

What `nf_award_requirements` is, what may enter it, and what it refuses.

## The table

```text
migration           0033_nf_award_requirements    head 0032 -> 0033
columns             32
CHECK constraints   19
indexes              3
foreign keys         5
RLS policy           nf_award_requirements_org_demo_scope   PostgreSQL only
rows                 0
```

The RLS predicate is the one twenty other tables carry, unchanged:

```sql
organization_id = current_setting('app.current_org_id', true)::uuid
AND is_demo = current_setting('app.current_org_is_demo', true)::boolean
```

## Two identifiers, and only one is authority

```text
organization_id    UUID, FK organizations CASCADE, the RLS anchor
awarded_grant_id   UUID, FK nf_awarded_grants CASCADE, a row relationship
```

Both are `NOT NULL` and they answer different questions. `awarded_grant_id` says
which award this obliges; `organization_id` says who may read the row.

Carrying only the award would be the substitution Gates 110–113 exist to refuse:
the policy reads `organization_id`, so a table without that column cannot be
scoped at all, and reaching the organization through a join would make every
policy here depend on a policy there. `awarded_grant_id` is therefore in
`FORBIDDEN_ANCHOR_NAMES` alongside `tenant_id`, `customer_org_id` and
`organization_profile_id` — required as a relationship, refused as authority.

Supplying the award without the organization is refused by its own name:

```text
awarded_grant_id_is_not_an_organization_id_anchor
```

The row carries **no tenant label at all**. Unlike an award, a requirement has
no tenant-facing identifier of its own; it inherits one through the award.

## Three booleans, one derivation, no inputs

```text
requirement_source                    active  projected  unsupported
human_entered / evidence_extracted    true    false      false
projected_from_nofo                   false   true       false
unsupported_document_type             false   false      true
unknown / needs_human_review          false   false      false
```

Gate 108 already derives this, in one line, from `extraction_status`. This gate
persists the derivation and refuses the contradiction in four CHECK constraints:

```text
ck_..._not_both_obligation_and_projection
ck_..._obligation_needs_capable_source
ck_..._projection_matches_source
ck_..._unsupported_matches_source
ck_..._unsupported_is_not_an_obligation
```

`prepare_requirement_write` has **no parameter** for any of the three — the
separation expressed as a signature, the way Gate 124 refused a projection
parameter on the awards side. A test asserts every name in `DERIVED_ONLY_FIELDS`
is absent from the signature.

## A projection is stored

The gate brief could be read as "refuse a projection". It does not. Two lists
answer two questions:

```text
blocked_reasons   this row may not be stored
refused_claims    this row is stored, and something it asserted was not
```

Recording what a NOFO projected beside the award it became is how a Tribe sees
what they expected against what they got. Refusing the row would also make
`projected_burden` an unreachable column and leave every "a projection is not an
obligation" test with no projection to test — the unreachable-branch pattern
this campaign has hit in Gates 117 through 121.

So a projection is stored, `active_obligation` derives to `False`, the refusal
is named in `refused_claims`, and `human_review_required` is true. The same for
a requirement extracted from a document nobody could read.

## The nineteen CHECK constraints

```text
type / status / source / due_date_status / recurrence          5 vocabularies
proof_status / submission_status / fact_status                 3 vocabularies
title_not_blank                                                a name is required
not_both_obligation_and_projection
obligation_needs_capable_source
projection_matches_source
unsupported_matches_source
unsupported_is_not_an_obligation
calculable_status_needs_a_date
date_needs_a_status
accepted_needs_submitted
accepted_proof_needs_a_reference
obligation_needs_established_facts
```

The Core `sa.Table` in `award_requirements_repository_service` restates all
nineteen. Gate 119C shipped a Core table with the columns and none of the
constraints; two tests now compare the definitions by name.

## An estimate is not a deadline

```text
DUE_DATE_STATUSES         verified, calculated, estimated,
                          unknown, unsupported, needs_human_review
DATE_CALCULABLE_STATUSES  verified, calculated
```

Gate 108 put `estimated` outside the calculable set. An estimated date is
stored, reported as estimated, flagged for a human, and never counted down to.

A document nobody could read cannot produce a verified date either: the status
is downgraded to `unsupported` **before** `date_is_calculable` is decided. That
ordering is load-bearing — computing the boolean first left an unreadable
document reporting a countdown-ready deadline, which is the exact thing
`DATE_CALCULABLE_STATUSES` exists to prevent, defeated by statement order. Three
invariants now guard it.

Nothing derives a date from a recurrence rule. "Quarterly" says how often; the
quarter boundaries a funder uses are in the award terms.

## Four things a proof is not

```text
a document reference is not a document      there is no document store
a document reference is not a submission    somebody has to file it
a submission is not an acceptance           somebody has to accept it
an acceptance is not a proof                unless a reference and a date exist
```

Each is a separate refusal with its own name. Collapsing any one of them
produces a screen telling a Tribe they are compliant when they are not.

`document_storage_available` is a constant `False`, injectable so the permitted
branch is reachable and the refusal is a measurement rather than a constant. A
reference supplied without a store is refused by name.

## The seven operations

```text
prepare_requirement_write            decides; touches no database
create_award_requirement             one INSERT, if prepare permits it
get_award_requirement                one row, anchored on organization_id
list_requirements_for_award          one award's rows, still org-anchored
list_requirements_for_organization   every row, across every award
archive_award_requirement            an UPDATE. Never a DELETE
validate_requirement_persistence     is what is stored fit for a calendar?
```

There is no upsert. A requirement that recurs is many rows, one per period,
because overwriting last quarter's row erases whether last quarter was met.

Listings order by due date and return archived rows by default: a listing that
hid a withdrawn requirement would make it indistinguishable from one that never
existed. `calendarable_count` is reported separately from `rows_read`, because
what a calendar can count down to is not the same as what is stored.

## Archive, never delete

```text
rows_deleted                 constant 0
sa.delete / .drop calls      0, asserted by parsing the module
```

Archiving sets `active_obligation` to `False` and leaves `requirement_source`
alone: the provenance stays, the obligation does not. `not_applicable` and
`waived` are statuses a funder's audit can read.

## What a production write requires

```text
customer_auth_live              false
verified_operational_binding    false
```

Both injectable, both false, named separately. The guard now lists
`write_award_requirement` in `LABEL_BOUND_OPERATIONS` for a reason specific to
this table: a requirement carries no tenant label of its own, so the only thing
relating it to a tenant is the award's binding. A requirement written against an
award whose binding nobody verified is a deadline attached to the wrong Tribe.

```text
rows in the application database        0
production award requirements created   0
production proof records created        0
```

## What this gate deliberately did not build

**The proof audit trail.** `PROOF_ACTIONS` has six verbs and one requirement
submitted, rejected, resubmitted and accepted is four rows with four actors and
four timestamps. Putting that on the requirement row would mean overwriting the
history — the one thing an audit trail may never do. It gets its own table in a
later gate, and `proof_audit_persistence_available` is measured rather than
asserted, so it moves on its own the day it exists.

**The document store.** `award_document_store_service` does not exist. Doc 598
listed it as next action 4 and it still is.
