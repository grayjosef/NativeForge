# 509 — Awarded-vs-pursuit lane contract and "Mark as Awarded"

**Status: queued requirement for Gate 91. Nothing in this document is built.**

Captured during Gate 90. Gate 91 does not exist yet — doc 508 queued it and it
has not been started — so this is the specification it will be built against,
not an addition to something already running.

## What exists today, and why it is the wrong shape

Searched before writing this, because a contract that describes an imaginary
system is worse than no contract.

```text
GrantPipelineStage  (domain/enums.py)
    new | evaluating | pursuing | drafting | submitted | awarded | not_pursuing

PURSUIT_STATUSES    (pursuit_workspace_contract_service)
    draft | under_review | needs_information | deferred | blocked | closed
```

`awarded` exists — as **one value in a pipeline-stage enum on a tracked Spark**.
There is no awarded-grant portfolio, no lane model, no transition service, no
undo, and no awarded UI anywhere in the frontend.

**The product rule this addendum states is currently violable by assignment.**
Today the only way a record becomes "awarded" is for something to set an enum
field — which is exactly backend classification, the thing the addendum says
must never be the sole route. Nothing stops it and nothing records who did it.

That is the gap Gate 91 closes.

## The product rule

> A pursued grant becomes an awarded-grant portfolio record only after an
> explicit user action or verified customer-provided award evidence.

Never from status text, source hints, or inference. This is the same rule the
campaign has applied to deadlines (Gate 87), corpus provenance (Gate 88) and
attestations (Gate 89), pointed at a different object: **a state change that
matters needs a person behind it, and the record must say who.**

Setting a pipeline stage is not that person.

## Why "awarded" is not just another stage

A pursuit is a *possibility*. An award is an *obligation* — reporting,
compliance, financial, performance and closeout duties that begin on award and
run for years.

Moving between them is not a status update, it is a change in what the customer
owes. The lane label says so: **Awarded Grants**, never "opportunities".

## Required UX

On any pursuit / submitted / award-pending record, expose:

```text
Mark as Awarded
```

On click:

1. **Confirmation**, stating what changes:
   - the record moves to Awarded Grants
   - reporting and compliance tracking begins
   - projected burden becomes *active obligation tracking* only after award
     details are entered
2. **Ask for minimum award details**: award date, award number, award amount,
   award start date, award end date, award document upload (optional)
3. **Allow "Skip for now"** — missing details become `HUMAN_REVIEW_REQUIRED`,
   not a failed transition
4. Move the record to Awarded Grants
5. Show **Undo**

### Copy

```text
Mark as Awarded

This will move the grant into your Awarded Grants workspace and start tracking
reporting, compliance, financial, performance, and closeout obligations. You can
undo this if it was a mistake.

Moved to Awarded Grants. Undo?
```

## Undo

Undo restores: prior lane, prior pursuit status, prior projected reporting burden
state, prior visibility in the pursuit pipeline.

Undo **must not delete**: uploaded award documents, the audit event, extracted
requirements, user-entered award details.

Those are marked **inactive / superseded** until the user says whether to keep or
remove them. This is the Gate 87/88 principle again — a reversal removes a
record's *standing*, never its evidence. A customer who marks an award by
mistake, undoes it, then marks it correctly a week later should not have lost
the document they uploaded the first time.

Undo must be **idempotent**. Clicking twice is not two reversals.

## Service to build

```text
src/nativeforge/services/award_transition_service.py

mark_as_awarded(...)
undo_mark_as_awarded(...)
build_award_transition_preview(...)
```

Fields:

```text
transition_id             customer_org_id           source_opportunity_id
from_lane                 to_lane                   prior_state_snapshot
award_details             created_awarded_grant_id  requires_human_review
missing_award_fields      undo_available            undo_expires_at
audit_event
```

Rules:

```text
- explicit user action required
- customer org required
- archived / not_pursued cannot be marked awarded without human review
- cannot mark as awarded without preserving prior state
- undo is idempotent
- undo never deletes evidence
- every transition emits an audit event
- missing award details produce human_review_required, not failure
```

`prior_state_snapshot` is what makes undo honest. Without it, undo is a guess
at what the record used to look like — and the campaign has spent five gates on
the difference between a reconstruction and a record.

## Projected burden vs active obligation

These must never be confused, and the distinction is the reason the transition
exists at all:

| | Projected burden | Active obligation |
| --- | --- | --- |
| when | before award | after award, with details entered |
| source | NOFO text (doc 508 lane) | award document and terms |
| status | an estimate | a duty with dates |
| if wrong | a bad pursuit decision | a missed federal deadline |

Marking as awarded starts the *tracking*. It does not convert a projection into
an obligation — award details do. A record marked awarded with "Skip for now"
carries `HUMAN_REVIEW_REQUIRED` and must not display projected dates as though
they were real reporting deadlines.

That is the failure this table exists to prevent: a customer reading an
estimated quarterly-report date as a real one and planning around it.

## Tests Gate 91 must include

```text
- clicking Mark as Awarded moves the pursuit record to the awarded lane
- the awarded record appears in the awarded-grant portfolio model
- the pursuit record no longer appears as an active pursuit
- undo restores the previous lane
- undo is idempotent
- undo does not delete uploaded documents or extracted evidence
- missing award details create HUMAN_REVIEW_REQUIRED
- archived / not_pursued cannot be marked awarded without review
- the transition preserves an audit event
- projected burden and active obligation are never conflated
- no code path can create an awarded record without a user action
```

That last one is the load-bearing test. Everything else checks the mechanism
works; that one checks the mechanism cannot be bypassed — and given `awarded`
already exists as an assignable enum value, it is the one most likely to fail
first.

## Sequencing

The addendum says to build the transition service in Gate 91 if cheap, and queue
it as Gate 92 if not. It is **not cheap**, for a reason worth recording rather
than treating as an estimate:

There is no lane model to transition between. `GrantPipelineStage` is a stage
field on a Spark, `PURSUIT_STATUSES` is a separate six-value vocabulary on a
workspace, and neither is an awarded-grant portfolio. Building
`mark_as_awarded` first would mean inventing the lane it moves records into,
inside a gate scoped to reporting-requirement extraction.

Recommended split:

```text
Gate 91  reporting requirements extraction contract     (doc 508)
         + awarded-vs-pursuit lane contract             (this doc, as spec)
Gate 92  award_transition_service + Mark as Awarded + undo
Gate 93  customer-facing "What You Are Signing Up For"
Gate 94  pursuit scoring with reporting_burden_fit
Gate 95  lifecycle calendar / compliance checklist workspace
```

Gate 92 also needs a customer-org and persistence story that does not exist yet
— `customer_org_id`, document upload and `undo_expires_at` all imply durable
storage, and production storage and customer persistence are both currently NO.
That is worth confirming before Gate 92 rather than discovering inside it.

## Relationship to doc 508

508 queues the extraction of *what obligations a NOFO imposes*. This document
governs *when a customer takes those obligations on*.

They meet at the transition: the projected burden 508 produces becomes the
active obligation tracking that this contract starts. Neither is built.
