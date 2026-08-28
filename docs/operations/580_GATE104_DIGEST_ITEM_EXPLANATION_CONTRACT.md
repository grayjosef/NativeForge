# 580 — Gate 104D: digest item explanation contract

`src/nativeforge/services/tenant_nofo_digest_item_explanation_service.py`

Why one opportunity appears in one tenant's digest, in language a grants officer
can act on and a lawyer can defend.

## Matches and exclusions are separate fields

```text
why_this_matches       populated from tenant_match_reasons
why_this_may_not_match  populated from tenant_exclusion_reasons
```

Different fields, different sources, and a row can carry both. Merging them into
one "relevance" paragraph is how a partial match with three disqualifying
conditions reads as a recommendation.

An excluded item with an empty exclusion list fails an invariant. A refusal a
tenant cannot interrogate is worse than no refusal.

## Nothing overstates eligibility

The headline is derived from what the underlying assessment actually said:

```text
matched             "Matches your tenant profile"
partial_match       "May match - some conditions are not established"
excluded            "Excluded for your tenant"
downgraded          "Downgraded for your tenant"
needs_human_review  "Needs human review before you act"
unknown             "Eligibility not established"
```

`eligibility_determined` is False on every explanation. This service describes an
assessment; it does not make one. `deadline_guaranteed` and
`reporting_requirements_verified` are False for the same reason.

## Unverified deadlines say unverified

`deadline_note` is derived from Gate 87's provenance status, never from the date:

```text
verified_deadline      "Deadline verified against the source record."
unverified_deadline    "shown as recorded, but not verified - confirm with
                        the source before relying on it"
suspected_placeholder  "appears in a large cluster with no fetch evidence
                        behind it and is likely a placeholder"
missing_deadline       "No deadline was recorded."
unknown_deadline       "Nobody has established where this date came from."
```

An invariant fails an explanation whose note says "verified against the source"
while the provenance says otherwise, and another fails an unverified deadline
that was not flagged in `blocked_reasons`.

## Unsupported reporting burden stays unsupported

Doc 570's rule: unsupported or unclear requirements are `UNKNOWN`,
`NEEDS_HUMAN_REVIEW` or `UNSUPPORTED_DOCUMENT_TYPE`, never a confident-sounding
summary. The note for an unsupported document type carries the literal string
`UNSUPPORTED_DOCUMENT_TYPE`, and an invariant checks it is there.

## The allowability cap survives to the surface

When the label is `requires_human_review` because the assessed cost was
NativeForge itself, `allowability_note` says so explicitly:

> Capped at requires_human_review because the assessed cost is NativeForge
> itself — a self-assessment always goes to a person.

**The presentation layer is exactly where a cap like that usually dies.** Gate
103F applied it; this gate carries it into the customer-facing text, and an
invariant fails any explanation that dropped it. A mutation removing the note was
introduced and caught.

## Eleven item statuses

```text
new_match  first_seen  high_fit_unreviewed  changed  approaching_deadline
newly_excluded  downgraded  needs_human_review  suppressed  unchanged  unknown
```

Resolved from the strongest signal present, with suppression outranking
everything — a suppressed item is reported as suppressed rather than as whatever
it would otherwise have been.
