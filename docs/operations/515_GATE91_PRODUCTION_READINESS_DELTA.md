# 515 — Gate 91: production readiness delta

Supersedes doc 507 (Gate 90) as the current readiness position.

## Readiness is unchanged

| | Gate 90 | Gate 91 |
| --- | --- | --- |
| controlled customer pilot | NO_GO | NO_GO |
| production rollout | NO_GO | NO_GO |
| login live | no | no |
| production storage | no | no |
| customer persistence | no | no |
| pen-test passed | no | no |
| live source coverage | none | none |
| sources monitored | 0 | 0 |

## Baseline X untouched

```text
total_records                 185
recorded_verified_records      18
live_records                    0
monitored_sources               0
baseline_quality_score     0.0865
improvement_claim_allowed   false
```

A test asserts all of it after Gate 91, because a new lane model and reporting
parser sitting beside the corpus is the kind of thing that could be mistaken for
corpus improvement.

## What Gate 91 built

Seven contract services and their invariants:

```text
grant_lane_separation_service                  pursuit vs awarded lanes
awarded_grant_portfolio_service                customer-specific obligations
pursuit_reporting_burden_projection_service    projected burden, clearly labelled
award_transition_service                       Mark as Awarded + undo
grant_document_attachment_inventory_service    document inventory, hashed
grant_document_text_extraction_service         seam over the Gate 81/82 parsers
grant_reporting_requirement_extraction_service obligations with evidence
```

The most consequential change is small: **`awarded` is no longer reachable by
assignment alone.** Before Gate 91 the only meaning of "awarded" was an enum
member anything could set. Now a portfolio record requires an explicit user
action, a customer org, and a preserved prior state, and it emits an audit
event. The enum still exists and can still be set — it simply no longer produces
anything.

## What is explicitly NOT live

```text
awarded-grant lifecycle live     NO   contract only, no persistence
reporting tracking live          NO   nothing is being tracked for anyone
attachment download live         NO   nothing fetched; local fixtures only
document parser production-ready NO   PDF has no backend; synthetic fixtures only
Mark as Awarded UI               NO   frontend has no reference to "awarded"
```

`build_portfolio` carries `lifecycle_tracking_live: False` as a constant with an
invariant behind it.

## Honest limits worth stating

**No UI exists.** `frontend/src/` contains no reference to "awarded". There is no
Awarded Grants page, no Mark as Awarded button, no undo toast. Gate 91 built the
contract those will call.

**No persistence exists.** `customer_org_id`, document upload and
`undo_expires_at` all imply durable storage. Production storage and customer
persistence are both NO, so nothing survives a process restart. This needs
resolving before Gate 92 rather than inside it.

**The parser has only been tested on synthetic documents.** Extraction over the
Gate 91 fixture yields 16 evidenced requirements, and the fixture was written to
exercise the extractor. Its behaviour on a real NOFO is unknown, and the repo has
no real NOFO with post-award reporting sections to find out from.

**PDF extraction does not work.** No backend is installed. Every PDF returns
`parser_unavailable` and escalates to manual review. Since a great deal of grant
burden lives in PDFs, this is a real limit on the lane rather than a detail —
installing a backend is a dependency decision for a future gate.

## The two threads, now three

```text
corpus provenance   (85-89)  18 of 185 records evidenced; blocked on an operator
                             attestation or surviving transport
source registry     (90)     55 candidate sources; blocked on terms review
lifecycle lane      (91)     seven contracts; blocked on persistence, a UI, and
                             real documents to read
```

The first two are blocked on human decisions outside the repo. The third is
blocked on engineering that has not been scoped — which makes it the only one
where more code would currently help.

## Recommended next

```text
Gate 92  persistence + Awarded Grants UI + Mark as Awarded / undo wiring
Gate 93  customer-facing "What You Are Signing Up For" profile
Gate 94  pursuit scoring with reporting_burden_fit
Gate 95  lifecycle calendar / compliance checklist workspace
```

Gate 92 should start by confirming the storage story, since three of Gate 91's
fields assume it.

## Status

```text
controlled customer pilot   NO_GO
production rollout          NO_GO
awarded-grant lifecycle     NOT LIVE
reporting tracking          NOT LIVE
attachment download         NOT LIVE
document parser             NOT PRODUCTION READY
login live                  no
production storage          no
customer persistence        no
pen-test passed             no
live SC coverage            none
live federal coverage       none
sources monitored           0
real live notices parsed    0
65% improvement claimed     no
```

Unchanged from Gate 90.
