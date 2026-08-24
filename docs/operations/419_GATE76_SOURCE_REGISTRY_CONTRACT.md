# 419 — Gate 76B: Source registry contract

## What is implemented

`src/nativeforge/services/source_registry_service.py` — a pure service. One
source record with a lifecycle, plus a per-source quality score.

The question it answers is *not* "which sources should we pursue" —
`source_candidate_registry_service` (829 lines, Sprint 37) already does that.
It answers **"is this source cleared to be monitored, and is it stale or
retired"**, which nothing did.

## What is not live

Everything. No source is fetched, no source is monitored,
`monitoring_active` is `False` on every record, and `last_checked_at` is only
ever what a caller supplies — the service never invents one.

## Vocabularies

**Source types** (12): `grants_gov`, `federal_agency_nofo_page`,
`federal_register`, `state_grant_portal`, `state_agency_page`, `foundation`,
`community_foundation`, `corporate_grants`, `native_intermediary`,
`university_research`, `local_regional`, `unknown`.

`opportunity_discovery_quality_service` (Gate 54) already has a 10-value
`SOURCE_TYPES` with different names for overlapping ideas
(`philanthropic_foundation` vs `foundation`, `native_specific_intermediary` vs
`native_intermediary`). Two vocabularies for one concept drift, so
`QUALITY_SOURCE_TYPE_MAP` bridges them explicitly and `quality_source_type()`
projects onto the scorer's set. Anything unmapped becomes `unknown` rather than
silently becoming something else. A test asserts every registry type projects
into the scorer's vocabulary.

**Promotion statuses** (9): `discovered`, `triaged`, `approved_for_monitoring`,
`monitoring`, `blocked_terms`, `blocked_low_quality`, `stale`, `retired`,
`unknown`.

Only `approved_for_monitoring` and `monitoring` permit monitoring.
`NON_MONITORING_STATUSES` is computed by set-difference, so a status added later
denies until someone deliberately permits it. A test asserts the partition.

**Robots/terms statuses** (6): `reviewed_allowed`,
`reviewed_allowed_with_rate_limit`, `reviewed_disallowed`,
`reviewed_requires_agreement`, `unreviewed`, `unknown`. Only the first two clear
monitoring.

## The monitoring gate

`can_monitor` is `True` only when the promotion status permits it **and** nothing
blocks it. Blockers:

```text
promotion_status_unknown
source_type_unknown
robots_terms_not_cleared:<status>
promotion_status_blocked_terms
promotion_status_blocked_low_quality
promotion_status_terminal:stale | retired
no_source_url
```

**Why this is in code rather than a runbook.** A source monitored before anyone
read its terms is a scraping incident that the site owner discovers before we
do. Runbook steps get skipped under deadline pressure; a function that returns
`False` does not. Four of the six robots/terms values deny.

A source marked `monitoring` that cannot actually be monitored gets an explicit
`marked_monitoring_but_not_eligible` blocker rather than being silently
downgraded — that combination is a data defect worth surfacing.

## Stale and retired behaviour

Both keep `visible: True`. A stale source that disappears from the registry looks
identical to a source we never had, which is how coverage silently shrinks
without anyone noticing.

They do not count toward *current* coverage quality: `score_source_quality`
returns `0.0` with a note naming the terminal status, and
`counts_toward_coverage` is `False`.

`retirement_status="retired"` overrides the promotion column. And a source with
no `last_checked_at` has `staleness_status="unknown"`, never `fresh` — absence of
evidence is not freshness, and an invariant fails any record claiming otherwise.

## Quality credit rules

Two hard preconditions, both returning a flat `0.0`:

1. **No provenance, no credit.** Without a URL showing where the claim came
   from, a score is an assertion.
2. **Duplicates score zero.** Raw source count must not be inflatable by
   re-listing the same portal under two names.

Otherwise five equally weighted components: provenance, terms reviewed (half
credit for a completed review that came back negative — being *known* has value),
typed, cadence declared, native rationale present.

Deliberately not a volume metric. A registry of 500 unprovenanced duplicates
scores zero.

## Invariants

`source_record_invariant_failures` fails, among others:

```text
monitoring_from_non_monitoring_status
monitoring_without_cleared_terms
monitoring_an_unknown_source_type
quality_credit_without_provenance
quality_credit_for_duplicate
staleness_claimed_without_a_check_timestamp
terminal_status_hidden_instead_of_visible
forbidden_claim:live_coverage_claimed
forbidden_claim:monitoring_active
```

## Not done here

Persistence. There is no migration and no table — the registry is a contract, and
persisting it needs its own migration with RLS policies plus an extension of
`verify_nativeforge_postgres_rls.sh`. Kept separate from migration 0028, which is
the audit schema.
