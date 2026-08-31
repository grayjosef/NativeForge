# 677 — Gate 126: the proof audit repository contract

What `nf_award_requirement_proof_events` is, what may enter it, and what it
refuses.

## The table

```text
migration           0034_nf_award_requirement_proof_events   head 0033 -> 0034
columns             26
CHECK constraints   16
indexes              3
foreign keys         6 (one of them a self-reference)
RLS policy           nf_award_requirement_proof_events_org_demo_scope
rows                 0
```

The RLS predicate is the one twenty-one other tables carry, unchanged:

```sql
organization_id = current_setting('app.current_org_id', true)::uuid
AND is_demo = current_setting('app.current_org_is_demo', true)::boolean
```

## The last post-award persistence lane

```text
Gate 124   nf_awarded_grants                    an award
Gate 125   nf_award_requirements                what it obliges
Gate 126   nf_award_requirement_proof_events    what was filed against it
```

Gate 108 built the proof/audit contract — `record_proof_action`,
`build_audit_trail`, 329 lines — and had nowhere to put an event.

## Three identifiers, one authority

```text
organization_id       UUID, FK organizations CASCADE, the RLS anchor
award_requirement_id  UUID, FK nf_award_requirements CASCADE, NOT NULL
awarded_grant_id      UUID, FK nf_awarded_grants CASCADE, nullable, context
```

Both relationship columns are in `FORBIDDEN_ANCHOR_NAMES` alongside `tenant_id`,
`customer_org_id` and `organization_profile_id`. The policy reads
`organization_id`; reaching it through two joins would make this table's policy
depend on two other tables' policies, which is the substitution Gates 110–113
exist to refuse.

`awarded_grant_id` is denormalised on purpose so a portfolio view need not join
through the requirement to reach the award. It is context, not a second
relationship, and each is refused under its own named reason:

```text
award_requirement_id_is_not_an_organization_id_anchor
awarded_grant_id_is_not_an_organization_id_anchor
```

## Append-first, and the two writes that are not

```text
create_proof_event      INSERT. The only way an event enters the trail.
supersede_proof_event   INSERT a new event, UPDATE the old one's superseded_at
archive_proof_event     UPDATE archived_at
```

`POST_INSERT_WRITABLE_COLUMNS` is `("superseded_at", "archived_at")` and both
are one-way. Everything else about an event is written once: what was believed
at the time is what the row says, forever.

There is no DELETE path. `rows_deleted` is a constant `0`, and a test parses the
module with `ast` looking for a call whose attribute is `delete` or `drop` —
Gate 123 found a substring search matching the sentence that explains the
absence.

## Superseding retains

Two rows change and neither loses anything:

```text
the NEW row       inserted, carrying supersedes_event_id
the REPLACED row  gains superseded_at, and keeps everything else
```

The replaced row keeps its reference, its timestamps and its actor, so an
auditor can read what was believed before the correction. A chain is ordinary:
if C supersedes B which superseded A, then B carries both a
`supersedes_event_id` and a `superseded_at`, which is why no constraint couples
them on one row.

`superseded_at` exists so "is this event current?" is a column rather than a
not-exists subquery against the whole table.

## The eight operations

```text
prepare_proof_event_write            decides; touches no database
create_proof_event                   one INSERT, if prepare permits it
get_proof_event                      one event, anchored on organization_id
list_proof_events_for_requirement    one requirement's trail, org-anchored
list_proof_events_for_organization   every event, across every requirement
supersede_proof_event                a new event, and the old one retained
archive_proof_event                  an UPDATE. Never a DELETE
validate_proof_event_persistence     is what is stored fit to read?
```

Listings return archived and superseded rows by default. A trail that hid either
would make them indistinguishable from events that never happened.

## The vocabulary this gate extended

```text
bridged from Gate 108   attach_proof, mark_submitted, mark_accepted,
                        mark_rejected, mark_waived, unknown
added by Gate 126       proof_requested, proof_needs_review,
                        proof_superseded, audit_note_added
```

Gate 108's `PROOF_ACTIONS` is imported as `BRIDGED_EVENT_TYPES` rather than
copied, and `vocabulary_invariant_failures()` refuses a vocabulary that has
dropped one of them. An extension that quietly became a replacement would leave
Gate 108's contract emitting actions this table cannot store, and the failure
would surface as an unstorable audit record rather than as vocabulary drift.

`event_status` is bridged whole from `PROOF_STATUSES` and not extended: what a
proof *is* has not changed, only what can happen to it.

## The sixteen CHECK constraints

```text
event_type / event_status / proof_source / fact_status     4 vocabularies
accepted_needs_a_timestamp
accepted_needs_submitted
accepted_needs_a_reference
rejected_needs_a_timestamp
rejection_retains_the_proof
not_accepted_and_rejected
supersede_names_its_predecessor
nothing_supersedes_itself
storage_flag_needs_a_store
review_pair
funder_decision_needs_established_facts
a_note_decides_nothing
```

`rejection_retains_the_proof` is the one worth naming. A rejection that erased
what was filed would make "we rejected it" indistinguishable from "nothing was
ever filed", and those are opposite facts about the same Tribe. The constraint
makes retention a property of the row rather than a promise in a docstring.

The Core `sa.Table` restates all sixteen. Gate 119C shipped a Core table with
the columns and none of the constraints; two tests compare the definitions by
name.

## Four things a proof event is not

```text
a document reference is not a document   there is no document store
a document reference is not a filing     somebody has to submit it
a filing is not an acceptance            a funder has to accept it
a note is not a decision                 a note records what somebody said
```

`proof_document_storage_available` is a column rather than a constant so a row
records what was true when it was written. It is false everywhere today, and
`document_store_present` is injectable so the permitted branch is reachable and
the refusal is a measurement rather than a constant.

## The requirement's proof status is derived, not written back

`derive_current_proof_status` folds a requirement's events — skipping superseded
and archived ones — and returns what its proof status is now. It is never
written onto `nf_award_requirements`: two writers on one column is how the two
come to disagree, and Gate 125's `proof_status` already carries its own CHECK
constraints. `written_back_to_requirement` is a constant `False` with an
invariant behind it.

An empty or fully superseded trail derives `not_submitted` rather than
`unknown`. Nothing being on file is a fact; reporting it as unknown would send a
human to look for something that is not there.

## What a production write requires

```text
customer_auth_live              false
verified_operational_binding    false
```

Both injectable, both false, named separately. The guard lists
`write_proof_event` in `LABEL_BOUND_OPERATIONS` for a reason specific to this
table: a proof event inherits its tenant through two hops — requirement, then
award — so the binding is the only thing relating it to anybody. A proof filed
against an unverified binding is one Tribe's evidence in another Tribe's file.

```text
rows in the application database   0
production proof records created   0
```

## What this gate did not build

**The document store.** `award_document_store_service` still does not exist.
`proof_document_ref` names a document and the reference resolves to nothing, so
the evidence itself is still wherever the Tribe put it. Doc 598 listed building
one as next action 4 in August and it still is.
