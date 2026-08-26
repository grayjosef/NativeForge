# 514 — Gate 91H: reporting requirement extraction contract

`grant_reporting_requirement_extraction_service` reads post-award obligations
out of deterministic document text.

## The rule, and why it is the whole module

**No obligation without evidence.**

Every requirement carries the quote that produced it, the character span it sits
at, and the document id it came from. A requirement whose quote is not in the
source text is **rejected by an invariant**, not merely warned about — and the
invariant re-checks the quote against the source rather than trusting the
extractor that produced it.

This matters more here than anywhere else in the campaign. *"Federal grants
generally require SF-425 quarterly"* is true as background and is **not** a
finding about a specific notice. A burden profile assembled from federal-grant
folklore would look authoritative, be unfalsifiable, and send a customer
planning around deadlines nobody imposed.

## Categories

```text
reporting_requirements     financial_requirements
performance_requirements   compliance_requirements
closeout_requirements      + application_requirements (separate)
                           + human_review_items
```

A sentence may match more than one category; each match becomes its own
requirement, so a quote is never split across categories.

## Three distinctions that survive extraction

### Application vs post-award

*"The application package must include a budget narrative with your
application"* is not a reporting obligation. Application-cued requirements go
into `application_requirements` and are **never** counted as burden. An
invariant fails if an application-timed requirement appears in a post-award
category.

A note on how that was built: the first version dropped the budget-narrative
sentence entirely, because it matched no category cue. Silently dropping an
application requirement *hides* it rather than separating it — so budget-document
cues were added to the financial set, letting the sentence be detected and then
routed by its timing.

### Recipient vs subrecipient

*"Subrecipients must submit quarterly financial reports"* binds somebody the
customer would pass money to, not the customer. Recorded per requirement,
defaulting to `unknown` rather than `recipient`.

### Required vs optional

*"Grantees are encouraged to report promising practices"* is guidance.
Obligation cues (`must submit`, `is required to`, `shall provide`) and optional
cues (`are encouraged to`, `may choose to`) are matched separately. Anything
without a clear obligation cue — or with both — is `unclear` and
`human_review_required`. An invariant fails on a non-required requirement that
is not flagged.

## No due date is ever produced

`due_date` and `first_due_date` are `None` on every extracted requirement, and
`dates_inferred` is a constant `0`.

A frequency is captured when stated — `quarterly`, `semi_annual`,
`within_90_days` — but **a frequency is not a deadline**. "Quarterly" does not
become four dated obligations. Dating requires a stated date or
customer-supplied award terms, and Gate 91C's calendar puts undated obligations
in their own list rather than computing them.

An invariant fails if extraction ever produces a date.

## Deterministic, non-AI

Literal cue phrases and regular expressions over text from the Gate 81/82
adapters. No model, no embedding, no classifier — checked by parsing this
module's imports with `ast`, not by grepping its prose.

Two runs over the same text serialise identically; a test asserts it.

## What it was tested against

`tests/fixtures/grant_documents/synthetic_award_terms.txt` — a synthetic award
terms document declaring itself a fixture on line 1, containing reporting,
financial, performance, compliance and closeout sections plus one subrecipient
duty, one optional-guidance sentence, and one application-time requirement.

Extraction over it yields 16 evidenced post-award requirements across all five
categories, 1 application requirement held separately, 1 subrecipient-bound
duty, and 5 human review items.

**A caveat worth carrying forward.** This is a synthetic fixture written to
exercise the extractor. The repo has no real NOFO with post-award reporting
sections — doc 508 recorded that a *useful* burden profile for a real customer
needs real notices, which needs monitoring, which needs terms clearance. The
contract is testable now; its output on real documents is not yet known.
