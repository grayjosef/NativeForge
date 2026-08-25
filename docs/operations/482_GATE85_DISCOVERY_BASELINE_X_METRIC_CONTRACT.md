# 482 — Gate 85B: Discovery Baseline X metric contract

`discovery_baseline_metric_contract_service` declares what Baseline X measures
and what it may never claim. It is declarative: nothing in it fetches and
nothing in it measures.

The split from the measurement exists so the shape of the baseline is reviewable
without the numbers, and so the forbidden claims are enforced by an invariant
rather than by discipline.

## Metric groups

| Group | Metrics |
| --- | --- |
| corpus composition | total, synthetic, recorded, live, unknown-source records |
| source coverage | total, monitorable, monitored, terms-cleared, robots-cleared, stale, retired, blocked |
| opportunity quality | evidence-backed, source URL, notice text, cited eligibility, cited exclusion, deadline, uncertain deadline, unparseable deadline, never checked, resolvable freshness, amendment evidence, duplicates, spam, honest-empty |
| applicant class | one row per class: the six `RESULT_STATES` counts plus negative intelligence |
| readiness | quality score, confidence level, production / demo / pilot usability, improvement-claim flag |

## Vocabulary rule

Every metric key is drawn from a frozenset that already existed:

```text
APPLICANT_CLASSES   eligibility_exclusion_evidence_service    8
RESULT_STATES       eligibility_exclusion_evidence_service    6
FUNDING_LANES       opportunity_funding_lane_service          8
FRESHNESS_STATES    opportunity_freshness_service             6
NOTICE_STATUSES     nofo_amendment_detector_service           9
```

Baseline X declares no new class, lane, state or status. `contract_invariant_failures`
fails if any of the four sets diverges from its canonical source, so a fork
cannot land quietly.

This is Gate 79B's lesson applied where it is most tempting to ignore. A
measurement layer looks like the safest possible place to declare a convenient
local list of applicant classes, and it is the worst: the numbers would keep
reporting cleanly while drifting away from the vocabulary the product actually
evaluates against.

## Forbidden claims

```text
improvement_claim_allowed
live_coverage_claimed
source_monitoring_claimed
fixture_mutation_performed
```

Each must be present and `False` on both the contract and any measured result.
`False` is required, not merely falsy — an absent key fails, because a claim
that was never declared is not a claim that was refused.

## Two invariant functions, not one

`contract_invariant_failures` checks the *declaration*. `baseline_result_invariant_failures`
checks a *measurement* against it, and enforces things a declaration cannot:

- corpus composition must sum to the total, so a bucket cannot go missing
- `live_records` must be zero — nothing here can produce a live record
- `monitored_sources` must be zero — no seed catalog carries a monitoring flag
- `production_usable` and `controlled_pilot_usable` must be `False`
- both recognition tiers must be present as separate rows
- every reported class, lane and freshness state must be canonical

Splitting them matters because the drift this gate guards against happens on the
measurement side. A contract stays honest on its own; a result acquires numbers,
and numbers acquire interpretations.

## Confidence levels

```text
none  <  synthetic_only  <  recorded_pre_live  <  live_partial  <  live_verified
```

Baseline X sits at `recorded_pre_live`, and that is the ceiling this corpus can
support: the records are frozen recordings of fetches from earlier gates, and no
source is monitored, so nothing is current by evidence.

## Deliberate nulls

`spam_or_low_quality_candidates` reports `None`, not `0`. No classifier for it
exists. A zero would say one ran and found nothing, which is a different and
false statement. The CSV renderer preserves the null as an empty cell rather
than coercing it, and a test pins that.
