# Discovery Baseline X

Measurement only. This document reports what the committed discovery corpus contains and what the existing machinery can say about it. It is not a target, a projection, or a claim of progress.

- Measured at: `2026-08-25T00:00:00Z`
- Confidence level: `recorded_pre_live`
- Schema: `nf_discovery_baseline_x_v1`

## Boundaries

| Claim | Value |
| --- | --- |
| `improvement_claim_allowed` | `false` |
| `live_coverage_claimed` | `false` |
| `source_monitoring_claimed` | `false` |
| `fixture_mutation_performed` | `false` |
| `network_access_performed` | `false` |

Nothing was fetched. Nothing was scraped. No committed fixture was modified. No source is monitored.

## Corpus composition

Deduplicated union of the committed corpora: **185 records**.

| Provenance | Records |
| --- | --- |
| recorded | 162 (87.6%) |
| synthetic | 0 (0.0%) |
| unknown | 23 (12.4%) |
| **live** | **0** |

`recorded` means a fetch happened during an earlier gate and the result was committed. It does not mean current. Nothing has been refreshed since, and nothing is monitored, so no record is current by evidence.

| Source file | Records | Contributed after dedupe |
| --- | --- | --- |
| `fixtures/real_grants_corpus/ta_mixed_tier13_grants.json` | 168 | 168 |
| `fixtures/real_grants_corpus/nf14_mixed_corpus.json` | 57 | 17 |
| `fixtures/real_grants_corpus/nf13_real_ingested_grants.json` | 40 | 0 |

## Source coverage

| Metric | Value |
| --- | --- |
| `total_sources` | 27 |
| `monitorable_sources` | 5 |
| `monitored_sources` | 0 |
| `terms_cleared_sources` | 0 |
| `sources_without_url` | 22 |
| `retired_sources` | 0 |

**0 sources are monitored.** No seed catalog carries a monitoring, robots or terms-review flag, so this is derived from the committed data rather than asserted. 22 of 27 seeds have no URL at all.

## What the machinery can say

| Metric | Records |
| --- | --- |
| `records_with_source_url` | 129 (69.7%) |
| `records_with_notice_text` | 108 (58.4%) |
| `evidence_backed_records` | 53 (28.6%) |
| `records_with_cited_eligibility` | 16 (8.6%) |
| `records_with_cited_exclusion` | 11 (5.9%) |
| `records_with_deadline` | 59 (31.9%) |
| `records_with_unparseable_deadline` | 19 (10.3%) |
| `records_never_checked` | 79 (42.7%) |
| `records_with_resolvable_freshness` | 0 (0.0%) |
| `records_with_amendment_evidence` | 0 (0.0%) |
| `honest_empty_records` | 23 (12.4%) |

`spam_or_low_quality_candidates` is reported as empty rather than zero. No classifier for it exists, and a zero would imply one ran.

**0 of 185 records have a resolvable freshness state.** The reasons split three ways: 79 have never been checked, 19 carry a deadline in a format the freshness evaluator cannot parse, and the rest have no close date at all. The deadlines were left as committed - normalising them here would manufacture freshness the pipeline cannot actually produce.

## Eligibility by applicant class

Reported per class, never collapsed. A notice open to a federally recognized tribe may exclude a state-recognized one, and a single combined answer would be wrong for one of them.

| Applicant class | eligible | excluded by evidence | not supported | unknown | review |
| --- | --- | --- | --- | --- | --- |
| `bie_funded_school` | 0 | 11 | 96 | 77 | 1 |
| `federally_recognized_tribe` | 19 | 0 | 89 | 77 | 0 |
| `native_business` | 1 | 11 | 95 | 77 | 1 |
| `native_individual` | 0 | 11 | 96 | 77 | 1 |
| `native_nonprofit` | 0 | 11 | 96 | 77 | 1 |
| `state_recognized_tribe` | 0 | 11 | 96 | 77 | 1 |
| `tribal_organization` | 23 | 1 | 84 | 77 | 0 |

Excluded records stay visible and counted. An exclusion found and cited is negative intelligence worth telling a customer about, not a row to hide.

## Funding lanes

| Lane | Records |
| --- | --- |
| `corporate` | 0 |
| `federal` | 112 |
| `federal_pass_through` | 0 |
| `federal_sc_relevant` | 0 |
| `foundation` | 2 |
| `local_regional` | 0 |
| `sc_state` | 0 |
| `unknown` | 71 |

## Readiness

| Gate | Value |
| --- | --- |
| `baseline_quality_score` | `0.0865` |
| `production_usable` | `false` |
| `controlled_pilot_usable` | `false` |
| `customer_demo_usable` | `true` |
| `improvement_claim_allowed` | `false` |

Per-class discovery quality score:

| Applicant class | score | eligibility evidence | negative intel |
| --- | --- | --- | --- |
| `bie_funded_school` | 0.3354 | 0.0 | 11 |
| `federally_recognized_tribe` | 0.3505 | 0.0757 | 0 |
| `native_business` | 0.3365 | 0.0054 | 11 |
| `native_individual` | 0.3354 | 0.0 | 11 |
| `native_nonprofit` | 0.3354 | 0.0 | 11 |
| `state_recognized_tribe` | 0.3354 | 0.0 | 11 |
| `tribal_organization` | 0.3505 | 0.0757 | 1 |

`baseline_quality_score` is 0.0865: the share of the 185 records for which the machinery can produce a cited eligibility or exclusion verdict. It is not the share of records that exist. Volume is not quality, and the gap between 185 records and 16 cited verdicts is the point of this document.

## What this baseline does not say

- It does not claim any source is being monitored.
- It does not claim any federal or South Carolina coverage is live.
- It makes no comparison to any earlier measurement.
- It does not convert relevance into eligibility.
- It does not treat an absence of exclusion as eligibility.

