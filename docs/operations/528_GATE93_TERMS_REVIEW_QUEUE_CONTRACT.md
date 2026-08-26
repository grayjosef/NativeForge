# 528 — Gate 93F: terms and legal review queue contract

**No collectors were activated. No URLs were fetched. No live coverage is
claimed.** Every queue item leaves with `review_status: pending` and
`automation_blocked: true`; `reviews_performed` and `sources_activated` are both
0.

## The gap this closes

Gate 90 flagged the rows. Gate 92 counted them: 148 `TERMS_REVIEW_REQUIRED` and
10 `HUMAN_REVIEW_ONLY`. Neither produced a **work list** — no reviewer, no
review status that could ever change, and no record at all of the four terms
pages whose text could not be retrieved.

A flag nobody can act on is a fact about the data. A queue is a fact about the
work.

## The queue

```text
queue length                    185   all pending, 0 approved

terms_review_required           118
human_review_only                62
terms_text_unretrievable          4
credential_and_role_required      1
login_required                    0
```

`118 + 62 = 180`, which is exactly Gate 92's `legal_terms_review_required_count`.
A test asserts the queue is a superset of every seed carrying that flag, so a
blocked source cannot fall out of the work list.

`login_required` reads 0 because Gate 92's seed service already classifies a
login-gated source as `human_review_only` — login is a human-only signal there.
The rows are queued, under the stricter label. The risk type stays in the
vocabulary for sources that become login-gated without that signal.

The 30-row gap between 148 flagged and 118 queued under `terms_review_required`
is rows that are *both* terms-review-required and human-only; they are queued
once, under the stricter classification.

## The four SPA terms pages are queue items, not footnotes

grants.gov, regulations.gov, usaspending.gov and reporter.nih.gov all serve
their terms client-side. The research pass retrieved **no policy text** from any
of them.

> **"No terms found" is not "no terms exist."**

They are seeded into the queue unconditionally — even from an empty registry, a
test asserts they appear — with `risk_type: terms_text_unretrievable` and
priority 1. An unread policy that nobody is tracking is indistinguishable from
one that was read and cleared, and the difference matters at production launch.

## SAM.gov is a credential item, not a terms item

Its terms are not ambiguous: scraping is prohibited outright, the API is the
sanctioned path. What blocks it is a **credential and role decision** —
10 requests/day without a SAM role, 1,000 with one. Filed as its own item so
the decision has an owner rather than being lost in a legal backlog.

## Deterministic

Items sort by `(priority, source_id)`; the id derives from the source id.
Nothing depends on iteration order, a timestamp, or a random value, so the same
registry produces byte-identical output — which is what lets the queue be
committed as an artifact and compared against a fresh generation.

## Nothing leaves the queue approved

An invariant fails any item whose `review_status` is `approved`, and any item
that is not `automation_blocked`. This gate creates work; it does not do it.
Approval is a human act, and there is deliberately no code path in Gate 93 that
can perform one.
