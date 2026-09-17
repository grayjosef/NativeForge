# Gate 162 — terms and human review facts

Where a human's answer about a source lives, and why there is one table.

## What was surveyed before adding anything

Four existing tables were candidates. Each records that a decision is
**required** and has nowhere to put the answer.

```text
nf_active_opportunity_sources
    legal_tos_review_required                 a requirement flag
    broad_eligibility_human_review_required   a requirement flag
    activation_approved_by / _at / _artifact  THE ACTIVATION DECISION -
                                              composed, not duplicated
nf_source_watchlist_entries
    human_review_required                     a requirement flag
    source_id (TEXT)                          the right id space, no answer
nf_discovery_review_items
    review_item_type includes source_verification
    review_status open/in_review/approved/rejected/merged/deferred
    source_registry_id -> nf_opportunity_sources.id  (UUID, 0 rows)
nf_review_artifacts                           org-level, not per-source
```

## Why `nf_discovery_review_items` could not be reused

It was the closest fit and it cannot be joined. Its `source_registry_id` is a
**UUID foreign key** into `nf_opportunity_sources`, which holds **0 rows**,
while the 177-row source registry is **file-backed and string-keyed**
(`nf-seed-2026-fed-001`).

Bridging those id spaces means creating opportunity-source rows, which is a
different gate's work and would **invent registry identity as a side effect of
recording a decision**. It also has no column for an expiry or for evidence
about the document reviewed, both of which a terms decision needs.

## Why ONE table for two questions

The first draft of migration 0048 gave terms its own table,
`nf_source_terms_decisions`. Then human review turned out to need exactly the
same shape: an answer, a signer, a time, an evidence reference, an expiry.

Two near-identical tables is not the minimum persistence this gate was asked
for. The migration was downgraded and rewritten as
`nf_source_authorization_decisions` with a `decision_kind` discriminator, and
the constraints are written once. Adding a third kind later costs a vocabulary
entry rather than a table.

`decision_kind` is **required and not defaulted** on every repository call. A
default would let a caller record a terms answer under the human-review
question by forgetting an argument.

## The decision vocabulary

```text
approved       the reviewer permits
denied         the reviewer refuses
needs_review   a reviewer looked and deferred
unknown        nobody has looked
```

`needs_review` and `unknown` are deliberately separate. One means "we are
waiting on a person", the other means "nobody has been asked" — different
problems with different owners and the same effect on permission, which is
precisely why a boolean will not do.

## The constraints that keep this gate honest

```sql
CHECK (decision <> 'approved' OR (reviewed_by IS NOT NULL
                                  AND reviewed_at IS NOT NULL))
CHECK (decision <> 'approved' OR evidence_fingerprint IS NOT NULL)
CHECK (decision <> 'denied'   OR reviewed_by IS NOT NULL)
CHECK (decision_kind <> 'terms' OR decision <> 'approved'
       OR guard_status IN ('NO_REVIEW_REQUIRED', 'ATTRIBUTION_REQUIRED'))
```

An approval nobody signed, or that names no evidence, **cannot be written at
all** — not by a service, not by a script, not by hand. The fact model refuses
one too, but a service can be bypassed and a CHECK cannot, and this is the
single row whose forgery would unlock a live source call.

A denial needs attribution as well, so "a human said no" stays distinguishable
from a row nobody owns.

There is deliberately **no** constraint forbidding `approved`. Gate 163 must be
able to write one for a source a human really reviewed. What is forbidden is an
approval without attribution and evidence.

The real organization is refused **by name** in the repository, because a terms
decision against it is exactly the row that would make a real source callable
outside the standing authorization.

## What the table will not hold

```text
no terms text          a sha256 fingerprint of the document reviewed
no URL                 a sha256 fingerprint, as Gate 160 settled - terms
                       URLs carry query strings
no credential          no header, no token, no cookie
no customer data
```

`notes_classification` is capped at 256 characters and is for a reviewer's
classification, not for quoting the document. Storing the terms text would make
this table a copy of somebody else's copyrighted page.

## One answer per source per question

Unique on `(organization_id, source_id, decision_kind)`. A re-review
**replaces** the answer, because two live answers to one question have no
defined winner and an append-only history needs a "which one counts" rule
somebody would eventually get wrong. The previous answer is not lost silently —
`record_decision` reports what it replaced.

## Freshness

Terms, human review and robots can go stale. A decision made against a document
that has since changed is not evidence about the current document, so an expired
affirmative answer becomes `stale` rather than staying `recorded`.

Credential, rate-limit, user-agent and collector facts are runtime state rather
than decisions, so they are measured fresh each time and carry no expiry.

## The verdict outranks the guard value

A reviewer who records `denied` naturally carries the guard status
`TERMS_REVIEW_REQUIRED` — the terms really do require review and the answer
really was no. The first draft derived fact status from the guard value alone
and reported that refusal as `needs_review`: "waiting on a human", about a
source a human had already refused.

The reviewer's verdict now travels with the fact and wins. The guard value
still decides what the guard is **told**; the verdict decides what the fact
model **says about it**.

## Activation is composed, not duplicated

`nf_active_opportunity_sources.activation_approved_by / _at /
_approval_artifact_id` remains the one place an activation decision is stored.
The resolver reads it, joined on `source_name` — because that table has no
`source_id` column and the file-backed registry has no UUID.

A name join is weaker than an id join and the resolver reports it as such
rather than quietly relying on it. **Gate 163 should give those two id spaces a
real key before it activates anything.**

An activation row with no signer reads as `activation_unknown`, not as
`activation_allowed`. A row exists and nobody signed it is not a decision.

## Current state

```text
real sources with a terms decision           0
real sources with a review decision          0
real sources approved                        0
unsigned approvals in the table              0
terms-blocked in the registry               171
human-review-blocked in the registry          6
```

Every decision this gate's verifier records is for a synthetic fixture under
the reserved `nf162.fixture.` prefix, and the verifier asserts by name that no
real source received one.
