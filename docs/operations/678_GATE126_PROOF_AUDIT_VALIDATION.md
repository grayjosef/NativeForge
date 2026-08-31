# 678 — Gate 126: proof audit validation

What makes a stored proof event fit to read as an audit record, and the four
defects found while building it.

## Four things this service will not work out for you

```text
a document reference is not a filing     somebody has to submit it
a filing is not an acceptance            a funder has to accept it
a review note is not a rejection         a note decides nothing
a document reference is not a document   there is no store behind it
```

Each is a separate refusal with its own name. Collapsing any one produces an
audit trail that tells a funder's auditor something nobody did.

## Retained, not removed

```text
rejected    the proof reference stays on the row
superseded  the prior event stays, and the new one points back
archived    the row stays and leaves the active view
deleted     nothing. There is no delete path
```

`proof_retained` is a constant, not a computation over the input — this service
removes nothing, whatever it is handed. Whether a *caller* discarded a reference
on a rejection is bad input, named in `blocked_reasons`; it is not the service
failing to retain anything. The distinction matters because it decides whether
the invariant behind it is a real one or a validation rule misnamed.

## The vocabulary this gate extended rather than forked

```text
bridged   attach_proof, mark_submitted, mark_accepted, mark_rejected,
          mark_waived, unknown
added     proof_requested, proof_needs_review, proof_superseded,
          audit_note_added
```

`BRIDGED_EVENT_TYPES` **is** `PROOF_ACTIONS`, imported. `vocabulary_invariant_failures()`
refuses a set that has dropped one of Gate 108's actions, and a test forges the
drop to prove the check fires.

## The four defects

### 1. An invariant fired on ordinary bad input

`a_proof_event_stopped_retaining_its_proof` read a `proof_retained` computed
over the caller's `event_status` and `proof_document_ref`, so a caller writing
`proof_rejected` with no reference tripped it — bad input, already named by
`rejection_discarded_the_proof_reference`.

Fixed by making `proof_retained` a property of the service rather than of the
input. It can now only go false if somebody changes the service, which is the
only way it *should* be able to.

### 2. An invariant fired on the permitted branch

`document_reference_not_storage` is False when a document store is present —
correctly, because a reference then resolves. The invariant compared it against
a constant `False`, so injecting a store to reach the permitted branch fired the
invariant on the one path the injection exists to test.

Two fields now, because they answer two questions:

```text
document_store_present               was a store supplied to this call?
document_storage_built_by_gate_126   no. Constant, with an invariant behind it.
```

The invariant compares the two: a reference resolves exactly when a store is
present. Both branches are now clean, and a test asserts each.

### 3. Five vacuous invariants

`proof_is_accepted` already requires a submission, a reference, a timestamp and
an established fact status. Three invariants restating those could never fail.
`proof_is_accepted and proof_is_rejected` could never both hold, because
`event_status` is one value. `acceptance_recorded and not submitted` was the
same shape.

An invariant that cannot fail is worse than none: it reads as coverage. Gate 125
found this shape twice; this gate found it five times, across the validation and
the repository.

### 4. A local that was a constant wearing a conjunction

```python
submitted_not_accepted = not (submission_recorded and accepted is None) or True
```

Always `True`, and unused. Removed; the derived claim lives in the result, where
something reads it.

## The rule, refined

Gate 125 adopted "an invariant may not read an echoed input", after Gate 124D
shipped three that ordinary bad input could trip. Gate 126 found the rule needs
one refinement and one companion.

**The refinement.** The rule's purpose is that bad input must never trip an
invariant — not that echoed fields are untouchable. An invariant guarded on
*storable* can read one safely, because bad input is never storable, and
comparing what the caller said against what the service derived is the only way
to catch the two drifting apart:

```python
storable = not blocked_reasons and not refused_claims
if storable and event_status == "proof_accepted" and not proof_is_accepted:
    failures.append("a_storable_acceptance_did_not_derive_as_accepted")
```

That is the only non-vacuous cross-check available here, and it needed the guard
to exist at all.

**The companion.** An invariant that restates a conjunction already inside the
value it checks can never fail. Both rules are now enforced by a test that
parses the invariant function with `ast`: the unguarded echoed names must not
appear, the derived ones must, and `submission_recorded` must be **absent**,
because the invariant that read it was one of the five vacuous ones.

## The validation matrix

Fourteen cases, written to
`award_requirement_proof_audit_validation_matrix.csv`. It includes
`a_valid_acceptance` alongside the two refused ones, so the permitted branch
appears in a durable artifact rather than only in a test.

## The artifact scans

```text
1  by field name  anything named like real award or tenant data
2  by inference   any result claiming an inference this campaign prohibits
3  by removal     any payload saying a record or a proof went away
4  by decision    any payload asserting a funder decided what the row does not
                  support
5  by capability  any payload whose capability claim disagrees with reality
```

The third is this gate's headline addition. An audit artifact asserting
`proof_deleted` or `audit_record_deleted` would be a file saying evidence
disappeared, and the entire reason this table is append-first is that it cannot.

The fifth is measured rather than frozen, and the reason is in doc 679.
