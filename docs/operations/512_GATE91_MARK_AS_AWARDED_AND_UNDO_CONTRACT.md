# 512 — Gate 91E: Mark as Awarded and undo contract

`award_transition_service` (`nf_award_transition_v1`) is the explicit customer
action that moves a grant into the Awarded Grants workspace.

## Why it exists

The product rule is:

> A pursued grant becomes an awarded-grant portfolio record only after an
> explicit user action or verified customer-provided award evidence.

Before Gate 91 that rule was unenforceable. `GrantPipelineStage.awarded` is a
plain enum member, assignable by anything, recording nobody — and it was the
only meaning "awarded" had in the codebase.

This service is where the rule becomes real.

## Explicit user action, required

`mark_as_awarded` **raises** without `user_action=True`, and raises again
without a `customer_org_id`.

A backend that infers an award from source text, a status string, or an enum
assignment cannot satisfy it. The enum can still be set — other code may depend
on it — but setting it does not route through here, so it creates no portfolio
record and records no actor.

**The load-bearing test** is `test_backend_enum_assignment_alone_is_not_a_valid_transition`:
it takes `GrantPipelineStage.awarded`, confirms the value exists, and proves
that neither passing it without a user action nor passing it *with* one produces
a transition — the raw stage value is not a lane.

## The customer-facing copy

Held as constants so the UI and the tests read the same strings.

```text
Mark as Awarded

This will move the grant into your Awarded Grants workspace and start tracking
reporting, compliance, financial, performance, and closeout obligations. You can
undo this if it was a mistake.

Moved to Awarded Grants. Undo?
```

Destination label: **Awarded Grants**. Never "opportunities".

`build_award_transition_preview` backs the confirmation dialog and changes
nothing — `transition_performed: False`, no record created, and an invariant
that fails if a preview ever produces an awarded grant id.

## Missing award details are a review item, not a failure

A customer may legitimately not have the award package to hand. "Skip for now"
is supported:

```text
transition_status        completed_with_human_review
requires_human_review    True
missing_award_fields     [award_number, award_start_date, ...]
obligations_dated        False
```

`obligations_dated: False` is the important one. The transition starts
*tracking*; it does not date anything. An invariant fails if obligations are
dated while award details are missing — which is what stops a customer reading
an estimated deadline as a real one.

## Archived and not_pursued need review

Marking an archived record as awarded is either correcting a mistake or making
one, and a person should say which. It is not refused — it produces
`transition_from_inactive_lane` in `human_review_reasons`.

Transitioning *from* an already-awarded lane raises.

## Undo removes standing, never evidence

Restores prior lane, status and visibility from `prior_state_snapshot`. The
snapshot is captured before anything moves — without it, undo is a guess at what
the record used to look like.

Preserved and marked `superseded`, never deleted:

```text
documents_deleted        0
requirements_deleted     0
award_details_deleted    0
audit_events_deleted     0
```

This is the Gate 87/88 principle applied to a user action. A customer who marks
an award by mistake, undoes it, then marks it correctly a week later should not
have lost the award letter they uploaded the first time.

**Idempotent.** A second undo returns `already_undone` and changes nothing
further. A third does the same.

An undo with no prior lane in the snapshot is *blocked* with
`no_prior_lane_in_snapshot` — it does not invent a destination.

## Audit

Every transition emits an immutable audit event carrying the action, actor,
customer org, both lanes, timestamp, and whether a user action was recorded.
Undo appends a second event rather than replacing the first.

An invariant fails on any transition without an audit event, without a customer
org, or without a prior-state snapshot.

## Not yet built

This is a contract and a service. There is **no UI** — no Awarded Grants page,
no Mark as Awarded button, no undo toast. `frontend/src/` contains no reference
to "awarded" at all.

Persistence is also absent, and Gate 92 will need it: `customer_org_id`,
document upload and `undo_expires_at` all imply durable storage, and production
storage and customer persistence are both currently NO.
