# 507 — Gate 90: production readiness delta

Supersedes doc 501 (Gate 89) as the current readiness position.

> **Superseded by Gate 91 (doc 515)** as the current readiness position.
> Nothing on this page changed: Gate 91 added the awarded-vs-pursuit lane
> contracts and the reporting parser seams, and moved no registry or corpus
> figure. 55 sources, 0 monitored, 0 URLs fetched; Baseline X still 185/18/0.
>
> Gate 91 added a third tracked thread: seven lifecycle contracts, none live,
> blocked on persistence and a UI rather than on a human decision. See docs
> 510-515.

## Readiness is unchanged

| Gate | Gate 89 | Gate 90 |
| --- | --- | --- |
| production_usable | false | false |
| controlled_pilot_usable | false | false |
| customer_demo_usable | true | true |
| live source coverage | none | **none** |
| sources monitored | 0 | **0** |
| improvement_claim_allowed | false | false |

## Baseline X is untouched

Gate 90 measured nothing about the corpus and moved nothing in it:

```text
total_records                  185
recorded_verified_records       18
recorded_asserted_records      166
recorded_circular_records        1
live_records                     0
monitored_sources                0
baseline_quality_score      0.0865
```

A test asserts every one of those after the registry import, because a new
source registry sitting beside the corpus is exactly the kind of thing that
could be mistaken for corpus improvement.

## What Gate 90 changed

The project now has a **list of 55 places it might one day look**, with the
blockers on each one written down.

```text
sources imported                55
sources monitored                0
URLs fetched                     0
scrapers activated               0
terms obligations or blockers   13
human-review-only sources        1
state-scoped sources            10  (all South Carolina)
software watchlist               3
```

This is the first gate in the 85–90 sequence that adds forward capability rather
than auditing backwards. It is worth being precise about how much: **a registry
is a to-do list, not coverage.** Nothing in it has been contacted.

## What it explicitly did not do

- **No URL was fetched.** A test greps the import service for every HTTP client.
- **No scraper was activated.** `monitoring_status` is the constant
  `not_started` on all 55 rows.
- **No live coverage is claimed.** Unchanged at none, federal and SC alike.
- **No monitoring is claimed.** `monitored_count` is 0 with an invariant.
- **No eligibility was determined.** Every row reads
  `NOT_DETERMINED_BY_REGISTRY`.
- **No allowability was determined.** Same.
- **No 65% improvement is claimed**, and the artifact writer refuses any
  document containing the phrase.

## The nearest-term unblocked work

**Terms review on 13 sources**, and one in particular.

`NAT-ATC` — the WHCNAA/BIA Access to Capital Clearinghouse — is the
highest-value Native-specific aggregator in the registry and is blocked on
`TERMS_REVIEW_REQUIRED`. It is `scraper_difficulty: high`, JavaScript-driven,
with `has_api: UNKNOWN`. Resolving its reuse terms and whether it exposes a
supported API is the single most valuable legal question available.

After that, 23 Tier 1 sources carry `low` risk and no login and could be built
behind nothing more than a robots check. `FED-GRANTS` needs an attribution
decision rather than a review.

## What still gates the pilot

Unchanged, and Gate 90 does not touch it:

```text
pilot readiness  needs current opportunities
currency         needs monitoring
monitoring       needs terms clearance
terms clearance  needs legal review, not engineering
```

Gate 90 makes the *first* step concrete — there is now a specific, prioritised
list of what needs clearing, with the risk bucket and login requirement recorded
per source. That converts "we need terms review" from a category into 13 named
items. It does not perform any of them.

## Two threads now, tracked separately

```text
corpus provenance  (Gates 85-89)  18 of 185 records evidenced; blocked on an
                                  operator attestation (doc 498) or surviving
                                  transport that the Gate 89 search did not find
source registry    (Gate 90)      55 candidate sources; blocked on terms review
```

Neither thread is blocked on engineering. Both are blocked on a human decision —
one an attestation, the other a legal review — which is the same conclusion Gate
89 reached, now confirmed from a second direction.

## Status

```text
controlled customer pilot   NO_GO
production rollout          NO_GO
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

Unchanged from Gate 89.
