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
| `records_with_raw_deadline` | 59 (31.9%) |
| `records_with_normalized_deadline` | 59 (31.9%) |
| `records_with_unparseable_deadline` | 0 (0.0%) |
| `records_with_ambiguous_deadline` | 0 (0.0%) |
| `records_never_checked` | 79 (42.7%) |
| `records_with_resolvable_freshness` | 19 (10.3%) |
| `records_with_amendment_evidence` | 0 (0.0%) |
| `honest_empty_records` | 23 (12.4%) |

`spam_or_low_quality_candidates` is reported as empty rather than zero. No classifier for it exists, and a zero would imply one ran.

## Deadlines and freshness

59 of 185 records carry a deadline. Every one of them normalizes to an ISO date, by one of three routes:

| Route | Records | What settled the format |
| --- | --- | --- |
| `exact` | 40 | already ISO; nothing to decide |
| `structural` | 13 | a field over 12 cannot be a month |
| `convention_declared` | 6 | the source's convention, asserted by the caller |

Raw and normalized are counted separately on purpose. Normalization rearranges digits that are already in the committed record; it cannot give a record a deadline it does not have, and an invariant fails if the normalized count ever exceeds the raw one.

### Can those deadlines be trusted?

Parsing a date and trusting it are different questions. Of the 59 deadlines the corpus carries:

| Provenance | Records | Meaning |
| --- | --- | --- |
| `verified_deadline` | 19 | checked, and pointing at a source |
| `unverified_deadline` | 0 | parsed, evidence incomplete |
| `suspected_placeholder` | 40 | does not behave like a fetched deadline |
| `unknown_deadline` | 0 | a value that does not resolve to a date |

**The raw deadline count overstates the trustworthy one by 40.** 40 records share a single identical date, and not one of them has ever been checked - while a comparable batch in the same corpus shows fifteen distinct dates across nineteen records, every one with a fetch timestamp.

`suspected_placeholder` is a suspicion, not a finding. Nothing says these dates are wrong - no local source establishes what the real deadline is, which is exactly why none of them can be called verified either. Every record stays visible, keeps its raw value unchanged, and carries its reasons. What the status blocks is a freshness state, not the record.

**19 of 185 records resolve to a freshness state.** A record earns one only by having both a normalized deadline and a timestamp saying somebody looked. 79 have never been checked, and no amount of parsing changes that.

Of the 19 that do resolve: **16 expired, 3 stale, 0 fresh.** Recovering these states did not make the corpus look better - it showed that the only deadlines anyone can check have all passed or gone stale. Those records stay visible and counted.

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

