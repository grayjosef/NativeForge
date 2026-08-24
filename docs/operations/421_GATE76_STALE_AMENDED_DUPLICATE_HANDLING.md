# 421 — Gate 76D: Stale, amended and duplicate handling

## The gap this closes

The survey found sixteen freshness-adjacent services. Every one of them answers
**source** freshness — "when did we last look at this page".
`source_freshness_service` (Sprint 15, 426 lines) has check intervals, next-due
computation, overdue detection and check-run bookkeeping. All of it is about the
source.

Nothing modelled **opportunity** freshness — "is this grant still open, was it
amended, has a newer version replaced it".

That distinction is not academic. A source checked an hour ago can serve a grant
that closed last month. Showing a tribal grant office an expired grant as current
is the failure that causes a missed deadline, which is active harm rather than a
missing feature. It is the single worst thing this product could do to a
customer, so it gets the strictest rules in the codebase.

## States

```text
fresh       open, checked recently                      → counts as current
amended     extension or amendment evidenced            → counts as current
stale       open, not checked for 30+ days              → does not count
expired     close date passed, no extension evidence    → does not count
superseded  replaced, with evidence                     → does not count
unknown     no close date, or never checked             → does not count
```

`CURRENT_STATES` is `{fresh, amended}` and `NON_CURRENT_STATES` is derived by
set-difference, so a state added later is excluded from currency until someone
deliberately includes it. A test asserts the partition, and a parametrised test
asserts no non-current state can be counted toward quality.

## Rules

**A close date in the past is expired.** Not "probably still open". Only
extension evidence moves it, and then to `amended`, not `fresh`.

**A missing close date is unknown, never fresh.** Absence of a deadline is
absence of information, not permission to assume.

**A missing check timestamp is unknown.** We cannot vouch for what we have not
looked at.

**Everything stays visible.** `VISIBLE_STATES` is the full state set. A grant
that vanishes from the interface looks identical to a grant we never found, and
an expired grant is still the correct historical reference for an application
that was filed against it.

## Evidence

Extension evidence kinds:

```text
amendment_notice_url
federal_register_notice_url
funder_announcement_url
operator_verified_extension
```

Every entry needs a recognised `kind` **and** a non-empty `reference`. A
recognised kind pointing at an empty string is an assertion wearing the word
evidence, and a test covers exactly that case. Unrecognised kinds are ignored
rather than trusted.

## Amendment handling

An `amendment_date` newer than the `posted_date` marks the opportunity
`amended`. Amended still counts as current — an amended grant is a live grant
with changed terms, and suppressing it would hide a real opportunity.

## Supersession

The strictest rule here, and deliberately so.

Supersession requires **both**:

1. **Matching lineage** — same source, same funder, same title.
2. **Evidence** — one of `same_opportunity_number`, `amendment_notice_url`,
   `funder_stated_supersession`, `operator_verified_supersession`.

Plus a sanity check: a "newer" version whose amendment date is not actually
later is refused with `newer_version_is_not_actually_newer`.

**Why matching lineage alone is not enough.** Agencies re-post similar programs
annually. Treating a new fiscal year's NOFO as superseding last year's would
erase a record that is still the correct reference for an in-flight application
— the customer would lose the document describing the terms they applied under.

**Why a claim without evidence does not hide the older record.** A supersession
asserted with no evidence leaves the freshness state unchanged, records
`supersession_claimed_without_evidence`, and sets
`human_review_required`. Removing a real grant from view on somebody's say-so is
worse than showing one extra record.

`older_remains_visible` is always `True`. Supersession changes what is *current*,
not what existed.

## Duplicate handling

Two levels, both scoring zero rather than reducing a score:

**Source level** (`source_registry_service.score_source_quality`): a duplicate
returns `0.0` with `duplicate_scores_zero`, and `counts_toward_coverage` is
`False`. Raw source count cannot be inflated by re-listing the same portal under
two names.

**Opportunity level** (`native_opportunity_discovery_service`): any
`duplicate_status` other than `unique` or `canonical` sets `is_duplicate`, blocks
the record, and makes `counts_toward_quality` `False`.

Duplicates stay visible with their `duplicate_group_id`. The group is how an
operator later decides which member is canonical; deleting duplicates would
destroy that decision.

`discovery_intake_dedupe_fingerprint_service` and
`funding_opportunity_intake_operator_duplicate_detection_service` already handle
*detecting* duplicates. This gate handles what a detected duplicate is worth,
which is nothing.

## What is not done

- No fetching, no parsing, no persistence.
- The NOFO parser that would extract these dates from a document is Gate 81.
  Today the dates are inputs.
- Duplicate *detection* improvements are Gate 83.
- The measured baseline is Gate 85 and must use the existing Gate 54 scorer.
