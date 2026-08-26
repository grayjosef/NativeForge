# 517 — Gate 92: Phase 1 collector spine contract

`source_spine_build_plan_service` declares the five sources the collector layer
will be built on, in build order, without activating any of them. Every entry
carries `collector_status: not_built` and at least one activation blocker, and
an invariant refuses a plan where that is not true.

Nothing in this gate collects. `collectors_built`, `collectors_active` and
`urls_fetched` are all 0, and `monitoring_started` and `live_coverage_claimed`
are both false.

## Build order is not priority tier

The v2 registry's `priority_tier` is a backlog priority across 381 rows. It is
not a build order, and building 381 collectors is not the plan. These five come
first because nothing else works without them.

```text
1  GRANTS-GOV-EXTRACT            corpus_of_record          bulk_extract
2  GRANTS-GOV-SEARCH2            delta_accelerator         public_api
3  FEDERAL-REGISTER-API          notice_feed               public_api
4  SAM-GOV-ASSISTANCE-LISTINGS   program_catalog           public_api_with_key
5  USASPENDING-API-V2            prior_award_intelligence  public_api
```

## The daily extract is the corpus of record

Extract-primary, API-secondary. The daily XML extract is the only unmetered,
complete, fully documented snapshot in the set, and the only source carrying
Estimated Synopsis Post Date, Fiscal Year, Archive Date, the 18,000-character
description and the 4,000-character Additional Information on Eligibility.

It is retained for **7 days only**. That single fact changes the failure
handling: a missed day is unrecoverable, so a failed fetch pages a human rather
than retrying into the retention window. Both `grants_gov_extract_retention_days`
and `grants_gov_missed_day_is_unrecoverable` are asserted by tests.

Search2 is a delta accelerator and must never become the corpus of record. It
has no documented date filter and no documented rate limit, but an explicit
right to block — the wrong combination to build a backfill on. An invariant
fails a plan in which Search2 is marked anything other than `delta_accelerator`,
and another fails a plan with more than one corpus of record.

## The Grants.gov attribution is a build requirement

Verbatim, and enforced character for character:

```text
This product uses the Grants.gov API but is not endorsed or certified by the
U.S. Department of Health and Human Services.
```

Any UI surface using the API must display it. Both Grants.gov sources carry it,
`must_store_attribution` is true on each, and an invariant fires if the string
is altered anywhere.

## SAM.gov: API with key, and the rate limit is the constraint

SAM.gov prohibits automated data gathering and web scraping outright, and names
the consequence — detection results in the account losing SAM.gov access. The
plan marks it `public_api_with_key`, `auth_required: True`, and carries
`scraping_prohibited_api_only` as an activation blocker, checked by an invariant.

```text
non-federal user, no SAM role      10 requests/day
with a SAM role                 1,000 requests/day
```

10/day is unusable. Obtaining a role is a prerequisite to building anything on
this source, which is why `sam_role_not_obtained` is a listed blocker rather
than an operational note.

## Federal Register and USAspending

Federal Register needs no key and includes Public Inspection endpoints, which
surface documents ahead of publication — the documentation confirms the
endpoints exist; the 1–3 business day lead time is the dossier's inference and
is labelled as such. Pagination is capped at the first 2,000 results, so every
backfill must be partitioned by date range.

USAspending is prior-award intelligence: which ALNs actually fund tribes, at
what dollar ranges, and whether peer Tribes have won them. It carries **zero**
NOFOs. A USAspending record may never be surfaced as an open opportunity.

## Retention is mandatory on every collector

```text
must_store_raw_payload    True
must_store_retrieved_at   True
must_store_source_hash    True
```

No exceptions, enforced per source. This is the same rule Gates 87–88 arrived at
for the corpus: a record whose transport evidence was not retained cannot later
be distinguished from one that was invented. Writing the rule before the
collectors means no collector gets to be the exception.
