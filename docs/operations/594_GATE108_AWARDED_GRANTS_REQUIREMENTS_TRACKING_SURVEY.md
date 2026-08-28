# 594 — Gate 108A: awarded grants requirements tracking survey

Written before any implementation. Every claim was reproduced by reading and
running the tree.

## Headline: this is far less greenfield than the brief assumes

Gate 91 already built the awarded lane. `award_transition_service` and
`awarded_grant_portfolio_service` exist, are 480 and 380 lines, and already do
most of what Gate 108B and 108C describe. Building them again would fork the
awarded lane in two.

```text
108B award record contract      EXISTS as awarded_grant_portfolio_service
108C award transition contract  EXISTS as award_transition_service
projected vs active separation  EXISTS as pursuit_reporting_burden_projection
evidence-quoted extraction      EXISTS as grant_reporting_requirement_extraction
basic reporting calendar        EXISTS as build_reporting_calendar
```

The genuinely missing half is per-requirement **tracking**: status, owner,
reminder schedule, proof of submission, and a calendar built over those.

## What already exists

### `award_transition_service` (Gate 91, 480 lines)

```text
mark_as_awarded          requires user_action=True; raises AwardTransitionError
                         if a backend tries to infer an award from a status
                         string or enum assignment
undo_mark_as_awarded     idempotent - an already-undone transition returns
                         already_undone and changes nothing further
PRESERVED_ON_UNDO        documents, extracted_requirements, award_details,
                         audit_events - marked superseded, never deleted
TRANSITION_STATUSES      completed, completed_with_human_review, blocked, undone
```

It also holds the customer-facing copy, so the UI and the tests read the same
strings. Gate 108C's requirements are, in substance, already met.

### `awarded_grant_portfolio_service` (Gate 91, 380 lines)

```text
LIFECYCLE_STATUSES          awarded_active, awarded_closeout, awarded_closed,
                            unknown
REQUIRED_AWARD_DETAIL_FIELDS award_number, award_start_date, award_end_date,
                            award_amount - missing any is a review item, never
                            a silent assumption
REQUIREMENT_CATEGORIES      reporting, financial, performance, compliance,
                            closeout
build_reporting_calendar    dated vs undated, dates_inferred: 0
build_risk_summary
build_portfolio
```

`_requirement_has_evidence` gates on `evidence_quote`, so an obligation without
quoted source text cannot be treated as dated.

### `pursuit_reporting_burden_projection_service` (Gate 91)

Every field is prefixed `projected_` and every result carries
`is_active_obligation: False`. **The projected-vs-active boundary already
exists** and is enforced at the projection end.

### `grant_reporting_requirement_extraction_service` (Gate 91)

```text
CONFIDENCES      quoted, cued, unclear
DUTY_HOLDERS     recipient, subrecipient, unknown
REQUIREMENT_FORCE required, optional_guidance, unclear
TIMING           post_award, application, unclear
```

Sentence-span based with quoted evidence.

## What does not exist

Searched across `src/` and `tests/`:

```text
proof_of_submission / proof_ref      0 occurrences anywhere
assigned_owner                       0 occurrences
internal_reminder_schedule           0 occurrences
per-requirement status tracking      none - requirements are list entries with
                                     evidence, not records with lifecycle
due_date_status vocabulary           none
extraction_status vocabulary         none
overdue / due-soon calculation       none
awarded grants UI                    none in frontend/src
```

So Gate 108D, 108E, 108F, 108G, 108H and 108I are genuinely greenfield, and
108B/108C are bridging work rather than new contracts.

## The identity fork, and why this gate sits on it

The single most important finding.

```text
customer_org_id   used by 3 services   grant_lane_separation,
                                       awarded_grant_portfolio, award_transition
                                       (Gates 90-91)
tenant_id         used by 13 services  the tenant beta lane (Gates 103-104)
no bridge exists between them
```

The Gate 108 brief specifies `tenant_id` on awarded records. The existing
awarded services require `customer_org_id` and refuse to build without it.

This is the same shape as the three pursuit-stage vocabularies Gate 104 found:
two lanes grew separately and now meet. It is **not** resolved here, and it is
deliberately not resolved by assumption.

The tempting move is to declare one tenant equals one customer org and derive one
id from the other. That is a product and data-model claim nobody has verified,
and a silent equivalence between two identity spaces is exactly the kind of
assumption that becomes a cross-tenant data leak later.

So Gate 108 carries **both ids explicitly**, requires the caller to supply each,
derives neither from the other, and records how they were related:

```text
tenant_org_binding_status   caller_supplied | unknown
```

An invariant fails any record claiming a binding it was not given. Reconciling
the two identity spaces is named as required follow-up work, not done here.

## Specific questions answered

```text
Can a pursued grant be marked awarded today?
    Yes. award_transition_service.mark_as_awarded, and it refuses without an
    explicit user_action.

Can it be undone?
    Yes, and idempotently. A second undo returns already_undone.

Does Awarded Grants track active obligations?
    Partially. Requirements are carried as evidence-bearing list entries on a
    portfolio record. There is no per-requirement lifecycle - no status, owner,
    reminder, or proof - so "we owe this" can be recorded but "who owes it, by
    when, and did we file it" cannot.

Are obligations tied to evidence?
    Yes. _requirement_has_evidence gates on evidence_quote, and the calendar
    refuses to date a requirement without it.

Can the system distinguish unsupported document type from unknown requirement?
    In the digest lane, yes - Gate 104 carries unsupported_document_type as a
    distinct status with the literal token in customer-facing text. In the
    awarded lane, no. That distinction has to be built here.

Does any service fabricate requirements from unsupported PDFs?
    No. Extraction is sentence-span based and every requirement carries a quote
    or a confidence of "unclear". Nothing invents a requirement from an
    unreadable document; it produces nothing instead.
```

## Greenfield vs reuse

```text
REUSE (bridge, never fork)
    award_transition_service              mark/undo, preservation, audit
    awarded_grant_portfolio_service       award record, lifecycle, evidence rule
    pursuit_reporting_burden_projection   is_active_obligation: False
    grant_reporting_requirement_extraction quoted evidence
    unified_audit_event_service           audit events

BUILD
    award_requirement_model_service       per-requirement lifecycle, owner,
                                          reminders, proof status, due-date and
                                          extraction status vocabularies
    award_requirements_calendar_service   calendar over tracked requirements,
                                          overdue/due-soon, confidence
    award_requirement_proof_audit_service proof attach and status transitions
    awarded_grants_requirements_readiness readiness, detected by import
    awarded_grants_demo_fixture_service   labelled demo awards
    awarded_grant_record_service          tenant-lane surface delegating to the
                                          Gate 91 portfolio record
    awarded_grants_requirements_artifact  six committed artifacts
```

## Vocabulary bridges required

New vocabularies must extend rather than restate:

```text
requirement_type      15 types requested; the portfolio's 5 REQUIREMENT_CATEGORIES
                      map onto them and are imported, not retyped
award_status          7 requested; the portfolio's 4 LIFECYCLE_STATUSES are a
                      subset and are imported
extraction_status     projected_from_nofo must line up with the projection
                      service's is_active_obligation: False
unsupported_document_type  bridged from the Gate 104 digest vocabulary, which
                      already owns the token
```

## The rule this gate exists to hold

An awarded record may exist long before anyone knows what it obliges. The system
must be able to say *we hold this award and we do not yet know what it requires*
without either inventing requirements or pretending the award is not real.

That means `requirements_extraction_status` of `unknown` or `needs_human_review`
is a normal, non-blocking state, and `active_obligations_created` stays false
until evidence or a person says otherwise.
