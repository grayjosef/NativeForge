# 365 — Gate 56: SC + federal discovery improvement plan (65% target)

Status: target contract implemented and tested. **Improvement is NOT claimed
achieved.**
Service: `src/nativeforge/services/sc_federal_discovery_improvement_service.py`
Tests: `tests/test_tenant_authority_discovery_gate51_57.py`

## The target, stated as arithmetic

```text
target_score = baseline_score * 1.65
```

`achieved` is `false` unless a **measured** current score clears the target
**and** every quality constraint holds. There is no path to `achieved` that
does not involve a measurement.

## Quality constraints

| Constraint | Limit |
| --- | --- |
| duplicate rate | ≤ 0.10 |
| stale source rate | ≤ 0.25 |
| missing metadata rate | ≤ 0.10 |
| provenance completeness | ≥ 0.90 |

A run that clears the numeric target while breaching any constraint returns
`achieved=false` with the specific reason. This is the anti-gaming mechanism: a
scraper that triples row count with duplicates and no provenance scores high on
volume and still cannot claim improvement.

## Current status

```text
baseline_score:   NOT MEASURED
target_score:     NOT COMPUTED
achieved:         false
improvement_claimed: false
```

No baseline has been measured against live data, because live ingest is not
claimed and the SC pack is curated-current. Calling `evaluate_improvement` with
no measurement returns `measured=false, achieved=false` and the reason
`no_measurement_available`. That is the honest current state and the contract
reports it rather than defaulting to something flattering.

## What measuring the baseline requires

1. A defined measurement window (start and end, recorded).
2. A source set with recorded provenance and timestamps for each source.
3. An opportunity set carrying `source_id`, `source_url`,
   `extraction_timestamp`, `native_relevance_evidence`, `eligibility_evidence`,
   `eligibility_state`, `recognition_tier`, `authority_requirements`,
   `funding_geography`.
4. `build_source_coverage_baseline` then `build_discovery_quality_score`
   (Gate 54) to produce the number.
5. `build_improvement_target` to freeze it as the baseline.

Steps 2 and 3 need the Gate 55 monitoring path, which needs storage and
security gates that remain NO_GO. That dependency is the reason the number does
not exist yet, and it should be stated that way rather than estimated.

## SC + federal in one workflow

`build_sc_federal_routing` reports both lanes from a single pass and never
merges them:

- `sc_state_count` and `federal_count` are separate
- `single_workflow=true`, `lanes_merged=false`
- `state_and_federal_recognition_collapsed=false`

**SC-specific does not mean SC-only.** A South Carolina Native organization
needs federal opportunities in the same queue as state ones; what must never
happen is the two being averaged into one undifferentiated count.

## Recognition routing

Routes: `federally_recognized`, `state_recognized`, `native_nonprofit`,
`native_business_economic_development`, `unknown`.

State-recognized and federally recognized are **never collapsed** — they carry
materially different eligibility consequences. `unknown` stays unknown and
`unknown_recognition_treated_as_eligible=false` is enforced by invariant.

## Categories

education · workforce · housing · health · culture/language · infrastructure ·
economic development · public safety · environment and natural resources ·
unknown.

## Proven by test

- target is exactly baseline × 1.65
- improvement requires a measurement
- score below target is not achieved
- duplicate-heavy increase does not count as improvement
- stale sources, missing metadata and weak provenance each block the claim
- a clean measurement above target **is** achieved (the contract can say yes)
- SC and federal lanes separated; unknown recognition never becomes eligible
