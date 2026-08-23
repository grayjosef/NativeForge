# 363 — Gate 54: Opportunity discovery quality baseline

Status: contracts implemented and tested.
Service: `src/nativeforge/services/opportunity_discovery_quality_service.py`
Tests: `tests/test_tenant_authority_discovery_gate51_57.py`

## Why a baseline exists

A 65% improvement claim is meaningless without a measured starting point and a
metric that cannot be gamed by volume. This gate defines the metric. Gate 56
defines the target against it.

**The governing rule: more rows is not better discovery.**

## Composite score

`discovery_quality_score` is a weighted sum of six components, each 0.0–1.0,
with weights summing to exactly 1.0 (asserted by invariant):

| Component | Weight | Measures |
| --- | --- | --- |
| `source_freshness` | 0.20 | share of sources with a recorded fresh timestamp |
| `native_relevance_evidence` | 0.20 | unique opportunities with Native-relevance evidence |
| `eligibility_evidence` | 0.20 | unique opportunities with eligibility evidence and a non-unknown state |
| `duplicate_penalty` | 0.15 | unique share of the raw set |
| `provenance_completeness` | 0.15 | unique opportunities with source id + url + extraction timestamp |
| `recognition_routing_completeness` | 0.10 | unique opportunities routed to a known recognition tier |

Every component except freshness is computed over **unique** opportunities, so
duplicates cannot inflate a numerator. `duplicate_penalty` then separately
scales the whole result by the unique share. Duplicating a good result set is
therefore strictly worse than not duplicating it — proven by test.

## Baseline metrics reported

source count · sources by type · source type coverage · fresh / stale /
unknown-freshness counts · stale source rate · raw and unique opportunity
counts · duplicate count and rate · missing metadata count and rate ·
SC-specific count · federal Native-relevant count · authority requirement
completeness · recognition routing completeness · Native relevance score ·
eligibility evidence score · duplicate risk score · source freshness score.

## Source types tracked

`grants_gov`, `state_grant_portal`, `tribal_or_state_agency`,
`local_or_regional`, `philanthropic_foundation`, `corporate_community_giving`,
`university_research_partnership`, `native_specific_intermediary`,
`federal_agency_native_relevant`, `unknown`.

`unknown` is excluded from the coverage denominator — an unclassified source
does not count as covering a category.

## Honesty rules, enforced not just documented

- unknown freshness is never counted as fresh (`unknown_counted_as_fresh=false`)
- unknown eligibility never counts as eligible
  (`unknown_eligibility_counted_as_eligible=false`)
- raw count is never quality (`raw_count_counted_as_quality=false`)
- Native relevance requires evidence, not a keyword guess
- missing provenance earns no quality credit
- `live_ingest_claimed=false` and `broad_coverage_claimed=false` on every score

Invariants fail the record if any of those flags is anything but `false`.

## Proven by test

- a duplicate-heavy set scores **lower** than the same set without duplicates,
  despite having a higher raw count
- missing provenance and missing evidence reduce the score
- stale and unknown-freshness sources produce a 0.0 freshness score
- unknown eligibility yields a 0.0 eligibility evidence score

## Not done

No baseline has been *measured against live data* yet, because live ingest is
not claimed and the demo pack is curated-current. The metric is ready; the
number is not asserted. See 365 for what measuring it would require.
