# 579 — Gate 104C: digest change detection contract

`src/nativeforge/services/tenant_nofo_digest_change_detection_service.py`

Compares two tenant snapshots. It fetches nothing and needs no live collection —
which is the point, because there is none.

## Change detection requires multi-snapshot data

Doc 570 flagged this first and Gate 104A confirmed it: "changed deadlines",
"amendments" and "newly excluded" all compare an observation to an earlier one,
and with no live collection there is no second observation.

The honest substrate is a pair of **recorded** snapshots, and `comparison_kind`
records exactly what was compared:

```text
fixture_to_fixture   two demo or recorded snapshots   <- everything today
fixture_to_live      a recorded baseline against a live observation
live_to_live         two live observations
first_seen_only      no previous snapshot at all
unknown              the snapshots do not describe themselves
```

An invariant fails any result claiming a live comparison, because no live
snapshot can exist. A digest built on `fixture_to_fixture` may not be described
as monitoring, and the label travels into the committed artifact.

## No baseline means first_seen, not new

The rule that stops a first run lying. With no previous snapshot, every eligible
row is being seen for the first time *by this comparison* — which is not the same
as the opportunity being new in the world.

```text
first_seen    its own change type
new_match     requires a previous snapshot, enforced by invariant
```

A first digest reporting forty "new" opportunities would be forty opportunities
that have existed for months. A mutation removing the guard was introduced and
caught.

## deadline_changed uses provenance, not date arithmetic

Gate 87 built `deadline_provenance_service` because the corpus contained deadline
clusters with no fetch evidence behind them. Exactly one of its five statuses
counts as verified.

So a date difference alone is **not** `deadline_changed`:

```text
both sides verified      -> deadline_changed
either side unverified   -> deadline_changed_unverified, routed to human review
```

That is the difference between "the deadline moved" and "two unreliable records
disagree". An invariant fails any `deadline_changed` whose provenance is not
verified, and another fails an unverified change that skipped human review.

Doc 570's third tension, resolved by consuming the service that owns the answer
rather than reading the dates.

## amended uses the existing amendment model

`classify_amendment` from `opportunity_deadline_and_amendment_model_service` does
the work. It already separates `MATERIAL_CATEGORIES` — deadline, eligibility,
funding amount, attachment — from cosmetic ones, and already handles the
`last_updated_date_or_created_date` field that makes "something changed"
ambiguous. This service bridges its categories rather than inventing a second
amendment vocabulary.

## Nothing is deleted

`removed_from_source` means a row present in the previous snapshot is absent from
the current one. It is an **observation**, not a deletion:

```text
deleted                 false
previous_row_preserved  true
previous_row            the whole prior row, carried on the change record
rows_deleted            0
```

Invariants fail a removal marked deleted and a removal that dropped its prior
row. Exclusions and downgrades likewise carry
`previous_eligibility_match_status`, so "it used to match" is always answerable.

## Twelve change types

```text
new_match      first_seen      deadline_changed   deadline_changed_unverified
amended        newly_excluded  downgraded         approaching_deadline
human_review_required          unchanged          removed_from_source    unknown
```

`approaching_deadline` fires only inside 30 days **and only on a verified
deadline** — an unverified date is not a countdown.
