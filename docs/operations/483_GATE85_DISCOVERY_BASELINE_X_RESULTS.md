# 483 — Gate 85C/85D: Discovery Baseline X measured results

Measurement only. Nothing below is a target, a projection, or a comparison to an
earlier state. Regenerate with:

```bash
./scripts/generate_nativeforge_discovery_baseline_x.sh
```

Artifacts land in `artifacts/discovery_baseline_x/` as `baseline_x.json`,
`baseline_x_summary.md` and `baseline_x_metrics.csv`.

## The denominator

The committed corpora overlap, so the measured population is the deduplicated
union by `grant_id`:

```text
ta_mixed_tier13_grants.json    168 records   168 contributed
nf14_mixed_corpus.json          57 records    17 contributed
nf13_real_ingested_grants.json  40 records     0 contributed
                                             ----
                                              185 measured
```

The curated demo packs, the NOFO showcase packs and the stage12 demo path are
outside this denominator on purpose. Someone chose those rows to show a
customer; counting them as discovery output would measure the curation rather
than the pipeline. Doc 481 lists them.

Measuring `ta_mixed_tier13_grants.json` alone would have been the tidier choice
and would have dropped 17 records — the label-spread and edge cases, which are
the rows most likely to depress the numbers. That is exactly why they are in.

## Corpus composition

| Provenance | Records |
| --- | --- |
| recorded | 162 (87.6%) |
| unknown | 23 (12.4%) |
| synthetic | 0 |
| **live** | **0** |

`recorded` means a fetch happened during an earlier gate and the result was
committed. It does not mean current. Nothing has been refreshed since.

The 23 `unknown` are `no_live_nofo` rows: a source was checked and carried no
notice. They are neither fabrication nor coverage, so they are also counted by
name as `honest_empty_records` rather than being allowed to read as either.

## Source coverage

| Metric | Value |
| --- | --- |
| total_sources | 27 |
| monitorable_sources | 5 |
| **monitored_sources** | **0** |
| terms_cleared_sources | 0 |
| sources_without_url | 22 |

Zero monitored sources is derived, not asserted: no seed catalog carries a
monitoring, robots or terms-review flag, so there is nothing that could set it.
22 of 27 seeds have no URL at all — mostly the SC catalog, which deliberately
carries none because no SC source was terms-cleared.

## What the machinery can say about the 185

| Metric | Records |
| --- | --- |
| records_with_source_url | 129 (69.7%) |
| records_with_notice_text | 108 (58.4%) |
| evidence_backed_records | 53 (28.6%) |
| records_with_cited_eligibility | 16 (8.6%) |
| records_with_cited_exclusion | 11 (5.9%) |
| records_with_deadline | 59 (31.9%) |
| records_with_unparseable_deadline | 19 (10.3%) |
| records_never_checked | 79 (42.7%) |
| **records_with_resolvable_freshness** | **0 (0.0%)** |
| records_with_amendment_evidence | 0 (0.0%) |
| honest_empty_records | 23 (12.4%) |

### The freshness result is zero, and it is a real finding

Not one of the 185 records resolves to a freshness state. Three distinct causes:

```text
79   never checked          no ingested_at at all
87   no close date          checked, but no application_deadline
19   unparseable close date checked, has a deadline, in MM/DD/YYYY
```

The third is the interesting one. Those 19 records carry a real deadline; the
freshness evaluator parses ISO-8601 and the corpus stores `07/24/2026`. The
deadlines were left exactly as committed. Normalising them inside the baseline
would have produced freshness numbers the pipeline cannot actually produce —
which is fabricating source freshness, just with an extra step.

The fix belongs in a date parser in a later gate, not in the measurement.

## Eligibility by applicant class

Reported per class, never collapsed.

| Applicant class | eligible | excluded by evidence | not supported | unknown | review |
| --- | --- | --- | --- | --- | --- |
| `bie_funded_school` | 0 | 11 | 96 | 77 | 1 |
| `federally_recognized_tribe` | 19 | 0 | 89 | 77 | 0 |
| `native_business` | 1 | 11 | 95 | 77 | 1 |
| `native_individual` | 0 | 11 | 96 | 77 | 1 |
| `native_nonprofit` | 0 | 11 | 96 | 77 | 1 |
| `state_recognized_tribe` | 0 | 11 | 96 | 77 | 1 |
| `tribal_organization` | 23 | 1 | 84 | 77 | 0 |

The federally recognized and state-recognized rows differ on every column, which
is the point. 19 notices in this corpus are cited-eligible for a federally
recognized tribe; none is for a state-recognized one, and 11 cite an exclusion.
A single collapsed verdict would have been wrong for one of those two customers
every time.

The 77 `unknown` per class are the records with no eligibility text. They stay
unknown; a relevance label is not an eligibility verdict.

## Funding lanes

| Lane | Records |
| --- | --- |
| federal | 112 |
| foundation | 2 |
| unknown | 71 |
| everything else | 0 |

`sc_state` is zero. The classifier refuses to assign state funding without a
cited source, and no committed record carries one.

## Readiness

| Gate | Value |
| --- | --- |
| baseline_quality_score | 0.0865 |
| production_usable | false |
| controlled_pilot_usable | false |
| customer_demo_usable | true |
| improvement_claim_allowed | false |

Per-class discovery quality score:

| Applicant class | score | eligibility evidence | negative intel |
| --- | --- | --- | --- |
| `federally_recognized_tribe` | 0.3505 | 0.0757 | 0 |
| `tribal_organization` | 0.3505 | 0.0757 | 1 |
| `native_business` | 0.3365 | 0.0054 | 11 |
| `bie_funded_school` | 0.3354 | 0.0 | 11 |
| `native_individual` | 0.3354 | 0.0 | 11 |
| `native_nonprofit` | 0.3354 | 0.0 | 11 |
| `state_recognized_tribe` | 0.3354 | 0.0 | 11 |

`baseline_quality_score` is **0.0865**: the share of the 185 records for which
the machinery can produce a cited eligibility or exclusion verdict — 16 records.
It is not the share of records that exist. The distance between 185 records and
16 cited verdicts is what this document is for.

## A defect this measurement caught in itself

The first working version of the baseline handed
`build_discovery_quality_score` the raw corpus records. That function has been
class-aware since Gate 79B, but it reads `excluded_classes` off the opportunity,
and no committed record carries that field. Every applicant class scored an
identical 0.15, and the entire exclusion model counted for nothing.

The fix is `enrich_for_scoring`, which projects each record into the scorer's
shape **per applicant class**, carrying that class's own verdict and the
exclusion set computed from the committed eligibility text. It builds copies;
the committed records are never mutated, and a test pins that.

The scores above are the corrected ones. `test_scoring_projection_is_class_aware`
fails if every class ever scores identically again.

Fields the corpus genuinely does not carry — `recognition_tier`,
`authority_requirements` — are left absent, which drives their score components
to zero. Filling them in would have raised the totals by inflating precisely the
components this baseline exists to report as empty.
