# 674 — Gate 125: award requirements validation

What makes a stored requirement fit for a compliance calendar, and the four
defects found while building it.

## Provenance decides everything

Gate 108 wrote the derivation this service persists:

```python
# award_requirement_model_service, line 308
is_active_obligation = extraction in ACTIVE_CAPABLE_EXTRACTION_STATUSES
```

`requirement_source` is that field, bridged by import rather than restated.
Three booleans follow from it and none is an input:

```text
requirement_source                    active  projected  unsupported
human_entered / evidence_extracted    true    false      false
projected_from_nofo                   false   true       false
unsupported_document_type             false   false      true
unknown / needs_human_review          false   false      false
```

`prepare_requirement_write` has no parameter for any of the three, and a test
walks every value in `EXTRACTION_STATUSES` against the derivation.

## The rules

```text
title        the one field that cannot be unknown
type         never guessed from the title. "Quarterly report" could be
             financial, narrative or performance, and the three have
             different proof
source       never inferred. `unknown` stays unknown and says so
due date     an estimate is recorded, shown as estimated, and never counted
             down to. Nothing derives a date from a recurrence rule
proof        a reference is not a document, a reference is not a filing, a
             filing is not an acceptance, and an acceptance needs both a
             reference and a date
```

## Two lists, and why they are not one

```text
blocked_reasons   this row may not be stored
refused_claims    this row is stored, and something it asserted was not
```

The first version put `projected_burden_is_not_an_active_obligation` into
`blocked_reasons`, which vetoed the row. That made `projected_burden` an
unreachable column: no projection could ever be stored, so no test asserting "a
projection is not an obligation" had a projection to assert about. The same
family as the unreachable permitted branches in Gates 117 through 121.

A projection is worth storing beside the award it became. So it is stored, the
derivation refuses the obligation, and the refusal is named.

## Every invariant reads a derived value

The structural rule this gate adopted, after Gate 124D had to split a claim from
its derivation to fix three invariants that ordinary bad input could trip.

An invariant is a statement the service can never violate. If it reads a field
the caller supplied, it is not that — it is a validation rule under the wrong
name, and it makes the real thing unfalsifiable. So:

```text
never read   proof_status, submission_status, submitted, accepted, rejected,
             requirement_due_date, proof_document_ref
read instead proof_is_accepted, acceptance_recorded, date_is_calculable,
             active_obligation, projected_burden, unsupported_requirement
```

A test parses `validation_invariant_failures` with `ast` and asserts the echoed
names do not appear. It caught two while it was being written.

## The four defects

### 1. An invariant fired on ordinary bad input

`active_obligation_without_established_facts` compared against
`ACTIONABLE_FACT_STATUSES`, which excludes `demo_fixture` — so every demo
requirement with `human_entered` provenance tripped it.

The database's own CHECK names three statuses, not two:

```sql
NOT active_obligation OR fact_status IN
  ('verified', 'tenant_supplied', 'demo_fixture')
```

A fixture row *is* established — established to be a fixture. Only `unknown` and
`needs_human_review` are unestablished. The invariant now reads a derived
`fact_status_supports_an_obligation` matched to the constraint exactly.

### 2. Two invariants read echoed inputs

`a_proof_was_accepted_without_a_reference` read `proof_status`, and
`an_acceptance_preceded_its_submission` read `accepted` and `submitted`. Both
duplicated validation rules that already name the problem in `blocked_reasons`,
and both fired on ordinary bad input.

Replaced by two derived values:

```python
proof_is_accepted   = proof_accepted AND a reference AND submission accepted
acceptance_recorded = accepted_at AND submitted_at AND not rejected
```

### 3. A vacuous invariant, twice

`acceptance_recorded and not submitted` could never fire — `acceptance_recorded`
is a conjunction that already includes `submitted`. Same for
`date_is_calculable and not requirement_due_date`.

An invariant that cannot fail is worse than none: it reads as coverage. Both
were replaced by genuine cross-checks between values derived separately —
`proof_is_accepted` (about statuses) against `acceptance_recorded` (about
timestamps), which needed a new blocked reason to make it unfireable-by-input:

```text
proof_accepted_without_an_acceptance_timestamp
```

### 4. Statement order defeated a rule

`date_is_calculable` was computed **before** an unsupported document's date
status was downgraded, so a requirement extracted from a document nobody could
read reported a countdown-ready deadline. The whole point of
`DATE_CALCULABLE_STATUSES`, undone by two statements in the wrong order.

The downgrade now happens first, and three invariants guard the result:

```text
an_estimated_date_was_reported_as_calculable
an_unsupported_documents_date_was_reported_as_calculable
a_calculable_date_outside_the_calculable_statuses
```

## The validation matrix

Fourteen cases, written to `award_requirements_validation_matrix.csv`. Each row
reports `active_obligation`, `projected_burden` and `unsupported_requirement`
side by side with `requirement_source`, and both `refused_claims` and
`blocked_reasons`, because a matrix that showed only refusals could not show a
claim being recorded and denied.

## The artifact scans

```text
1  by field name     anything named like real award or tenant data
2  by inference      any result claiming an inference this campaign prohibits
3  by promotion      any payload asserting an obligation the source does not
                     support, or a countdown on a date nobody verified
4  by capability     any payload claiming a document store or a proof audit
                     trail, neither of which exists
```

The third checks the *pair* rather than either field alone — Gate 124H's
lesson, since most of these cases exist to show a claim being refused:

```text
active_obligation  requirement_source                    verdict
true               human_entered / evidence_extracted    supported
true               anything else                         refused
true               alongside projected_burden true       refused
```

The fourth is this gate's. It exists because Gate 125 builds a column that
*names* a document and imports a vocabulary that *describes* proof actions,
without building either store. A file asserting `document_storage_available`
would be read as "the evidence is filed somewhere" by everything downstream, and
the evidence is nowhere.
