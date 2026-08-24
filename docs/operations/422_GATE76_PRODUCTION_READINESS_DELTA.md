# 422 — Gate 76H: Production readiness delta

Gate 76 built the source registry and Native opportunity discovery contracts. It
fetched nothing, monitored nothing, and measured nothing.

## Source registry: now

| | Before | After |
| --- | --- | --- |
| A source record with a promotion/retirement lifecycle | no | yes, 9 statuses |
| Robots/terms gating monitoring | **no** | **yes, enforced in `can_monitor`** |
| Provenance required for quality credit | partial, per-service | yes, at the record |
| Duplicate scores zero | implied by Gate 54 scorer | explicit at source level |
| Stale/retired sources stay visible | undefined | yes, invariant-enforced |

The control that matters most: **unresolved robots/terms blocks monitoring.**
It lives in `can_monitor`, not in a runbook, so it cannot be skipped under
deadline pressure. Four of the six `robots_terms_status` values deny.

## Live source coverage: now

```text
Live source coverage:      NONE
Sources monitored:         0
Sources fetched:           0
Seed catalog entries:      14 (categories and placeholders)
Seed entries monitorable:  0
Seed entries with a URL:   2 (grants.gov, Federal Register — public record)
```

Twelve of the fourteen seeds have `source_url=None` on purpose. A
plausible-looking state portal URL would be a fabricated source, and
`source_seed_real_url_guard_service` exists because that has been a problem
before in this repo.

## Native relevance: now

Sixteen `native_relevance_classification_*` services already existed and were
**not** reimplemented — their evaluator already separates a keyword hit from a
structured signal, and a second opinion would drift.

What is new is the enforcement of what may be concluded:

- Relevance credit requires **evidence with a reference**. A recognised evidence
  kind pointing at an empty string is not evidence.
- **Keyword-only matches get no credit**, even when the label is strong.
- Weak labels get no credit regardless of evidence.
- **Eligibility is never inferred from relevance.** Relevance is about the
  program; eligibility is about the applicant. An opportunity can be
  unmistakably Native-relevant and still not say whether a given organization
  may apply — that resolves to `possibly_eligible` at best, with human review.

### A modelling correction worth recording

The requested recognition-routing vocabulary mixed two orthogonal axes: who the
applicant is (`federally_recognized`, `state_recognized`, `native_nonprofit`,
`native_business`) and what the money is for (`native_housing`, `native_health`,
`native_education`, `native_culture`, `native_infrastructure`).

A federally recognized tribe can pursue a housing grant. Forcing one value per
opportunity would discard whichever axis lost — and discarding the applicant axis
would silently narrow eligibility for a real tribal government. Routing is
therefore a **set**, with `recognition_tier` and `native_sectors` derived as
projections. The tier projection reuses the existing 4-value `RECOGNITION_TIERS`
rather than forking it.

## Stale / amended handling: now

This was the clearest genuine gap. Sixteen freshness-adjacent services existed
and all of them answered *source* freshness — "when did we last look at this
page". Nothing modelled **opportunity** freshness.

The distinction is not academic: a source checked an hour ago can serve a grant
that closed last month. Showing a tribal grant office an expired grant as current
is the failure that costs them a deadline, which is active harm rather than a
missing feature.

```text
close date passed, no evidence     → expired      (not current)
close date passed, extension cited → amended      (current)
open, checked recently             → fresh        (current)
open, unchecked 30+ days           → stale        (not current)
amendment newer than posted        → amended      (current)
no close date                      → unknown      (not current)
never checked                      → unknown      (not current)
superseded, with evidence          → superseded   (not current)
superseded, claimed without evidence → unchanged + human review
```

Supersession requires evidence **and** matching lineage. Same source, title and
funder is not sufficient — agencies re-post similar programs annually, and
treating a new fiscal year's NOFO as superseding last year's would erase a record
that is still the correct reference for an in-flight application.

Everything stays visible. A grant that vanishes looks like a grant we never
found.

## Owner-blocked

- Real `OIDC_*` credentials (Gate 69) — still the largest single unblock
- Managed PostgreSQL and `DATABASE_URL`; migration 0028 approval
- **Robots/terms review decisions per source** — a legal/policy judgement, not
  an engineering one, and the gate that stands between this registry and any
  fetching at all
- Whether to pay for a Grants.gov API key or use the public bulk feed
- Backup automation, PITR, restore drill; pen test; Slack webhook

## Engineering-blocked

- Enumerating actual federal agency NOFO pages and SC portals (research work)
- Source registry persistence — needs its own migration and RLS policies
- The scheduler with rate limiting and a review queue (Gate 80)
- NOFO parser and amendment detector (Gate 81)
- Duplicate and spam control (Gate 83)
- Customer correction loop (Gate 84)
- **Measured baseline X (Gate 85)** — must use the existing Gate 54
  `opportunity_discovery_quality_service`, not a second scorer
- The 65% improvement campaign (Gate 86), which cannot start before X exists

## Claims

```text
Live source coverage:      NONE
Coverage complete:         NOT CLAIMED
65% improvement:           NOT CLAIMED
Baseline X measured:       NO
Controlled customer pilot: NO_GO
Production rollout:        NO_GO
Customer login live:       NO
Production storage live:   NO
Customer persistence:      NO
Pen-test passed:           NO
```

## Controlled customer pilot delta

**None.** This gate improved the honesty and structure of funding intelligence.
It did not add a single monitored source, and a discovery engine with zero
monitored sources discovers nothing.

What genuinely changed: a source cannot be monitored before someone reads its
terms, an expired grant cannot be counted as current, a keyword cannot become
eligibility, a duplicate cannot inflate coverage, and state and federal lanes
cannot be collapsed. Those are the properties that make the eventual coverage
work trustworthy rather than merely large.
