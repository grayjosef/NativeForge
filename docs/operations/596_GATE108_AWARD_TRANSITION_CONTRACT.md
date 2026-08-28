# 596 — Gate 108C: award transition contract

`src/nativeforge/services/award_transition_service.py`

## Additive, because Gate 91 already got this right

`mark_as_awarded` and `undo_mark_as_awarded` have existed since Gate 91, with a
934-line test file behind them. Gate 108 adds a tenant-lane surface and changes
nothing above it.

```text
mark_awarded_for_tenant       delegates to mark_as_awarded
undo_mark_awarded_for_tenant  delegates to undo_mark_as_awarded
```

Delegation rather than reimplementation means the user-action requirement, the
evidence preservation and the audit event are Gate 91's single implementation,
not a second one that can drift from it. Gate 91's 67 tests still pass unchanged.

## Mark as awarded preserves pursuit and source history

```text
pursuit_history_preserved   true
source_history_preserved    true
pursuit_record_deleted      false
source_opportunity_deleted  false
evidence_deleted            false
```

Inherited from Gate 91's `PRESERVED_ON_UNDO` — documents, extracted
requirements, award details and audit events are marked superseded, never
removed.

## A backend may not decide a grant was awarded

Gate 91's rule, and it still holds: `user_action=True` is required, and
`mark_as_awarded` raises rather than inferring an award from a status string or
an enum assignment. `mark_awarded_for_tenant` additionally raises without a
`tenant_id`, because an awarded record with no tenant is every tenant's.

## Undo is idempotent

```text
first undo    undone
second undo   already_undone
third undo    already_undone
```

Idempotency is inherited rather than reimplemented. An undone transition reports
`awarded_record_created: False`, and an invariant fails one that still claims a
record.

A mistaken award destroys no evidence. That is the point of the undo: a misclick
should be reversible without costing the tenant their document history.

## A transition creates a record, never a duty

The rule the awarded workspace turns on.

```text
active_obligations_created   false, always, on both mark and undo
```

Marking a grant awarded means the tenant holds an award. It does not mean anyone
knows what that award requires. Obligations arrive later, from evidence or from a
person, through the requirement model — never as a side effect of the transition.

An invariant fails any transition claiming otherwise, and a mutation setting the
flag true is caught.

## A default that was invented, and then was not

An early draft defaulted `from_lane` to `"pursuing"`. That string is not in
`PURSUIT_LANES` — the real vocabulary is `pursuit`, `application_in_progress`,
`submitted`, `award_pending` — so every call that did not override it would have
raised.

It is the same forking mistake this campaign keeps finding, in miniature: a
plausible-looking value written from memory instead of taken from the vocabulary
that validates it. The default is now `award_pending`, and a test asserts it is a
real member.
