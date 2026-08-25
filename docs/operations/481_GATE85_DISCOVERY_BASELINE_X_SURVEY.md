# 481 — Gate 85A: Discovery Baseline X survey

Surveyed before writing any measurement code. The governing rule for this gate:
**Baseline X measures what exists; it does not create anything to measure.**

## Opportunity corpora (committed, `fixtures/`)

| File | Records | Provenance |
| --- | --- | --- |
| `real_grants_corpus/ta_mixed_tier13_grants.json` | 168 | recorded — the mixed tier-1/2/3 corpus |
| `real_grants_corpus/la_scaled_federal_grants.json` | 76 | recorded federal |
| `real_grants_corpus/ta_tier3_foundation_grants.json` | 66 | recorded foundation |
| `real_grants_corpus/nf14_mixed_corpus.json` | 57 | recorded |
| `real_grants_corpus/nf13_real_ingested_grants.json` | 40 | recorded |
| `real_grants_corpus/ta_tier2_state_grants.json` | 26 | recorded state |
| `real_grants_corpus/nf15_eligibility_reingest_pulls.json` | 2 | recorded evidence (SAMHSA SM-26-024) |
| `sc_monday_demo/*_curated_current_opportunity_pack.json` | 15 + 18 + 3 | curated demo packs |
| `nofo_showcase/*.json` | 2 + 1 + 3 | curated intelligence packs |
| `stage12_demo_path/opportunities.json` | 4 | synthetic demo |

Those files overlap, so the honest denominator is the deduplicated union, not
any single file and not their sum. Measured by `grant_id`:

```text
ta_mixed_tier13_grants.json   168   = la_scaled_federal 76 + tier3 66 + tier2 26
nf13_real_ingested_grants.json 40   entirely contained in the 168
nf14_mixed_corpus.json         57   40 shared with the 168, 17 unique
                              ----
deduplicated union            185
```

Baseline X measures the **185**. Picking the round 168 would have quietly
dropped 17 records, and those 17 are the label-spread and edge cases - the rows
most likely to make the numbers look worse, which is exactly why they have to
stay in.

Provenance flags on the union, straight from the committed data:

```text
real_fetch: true,  fetch_mode: live           145
real_fetch: false, fetch_mode: fixture         17   from a recorded pull fixture
real_fetch: false, fetch_mode: no_live_nofo    23   honest-empty: source checked,
                                                    no live notice found
never_synthesized: true                       185   all of them
fixture: true                                  17
```

**None is live now.** The 145 record a fetch that happened during an earlier
gate and has not been refreshed since; nothing is monitored, so nothing is
current by evidence. The Gate 78E write-back lockdown plus a passing
fixture-cleanliness verifier prove no test run mutates any of it.

The 23 `no_live_nofo` rows deserve care: they are not fabrications and not
recordings of a notice - they record that a source was checked and had nothing.
Baseline X buckets them as unknown provenance and also counts them by name as
`honest_empty_records`, so they cannot be read as either coverage or padding.

### What is deliberately outside the denominator

Three groups of files appear in the table above and are **not** measured:

```text
sc_monday_demo/*_curated_current_opportunity_pack.json   curated for the demo
nofo_showcase/*.json                                     curated intelligence packs
stage12_demo_path/opportunities.json                     synthetic demo path
nf15_eligibility_reingest_pulls.json                     2 evidence pulls, not opportunities
```

The curated packs are demo content: someone chose those rows to show a
customer. Counting them as discovery output would measure the curation, not the
pipeline. The nf15 file holds evidence records for a single re-ingest, not
opportunities.

This exclusion is stated rather than silent because it moves the denominator,
and a denominator that changes without explanation is how a baseline stops
being comparable to itself.

## Applicant profile fixtures

```text
sc_pilot/sc_tribal_profiles.json    10
nm_pilot/nm_tribal_profiles.json    22
ok_pilot/ok_tribal_profiles.json    38
wa_pilot/wa_tribal_profiles.json    29
org_applicant_profile/demo_records.json   6
```

Profiles, not opportunities. Out of scope for corpus composition but relevant
to applicant-class measurement.

## Synthetic notice fixtures (Gate 81/82)

```text
tests/fixtures/nofo_text/        7 files   synthetic notices, self-declared
tests/fixtures/nofo_artifacts/   6 files   synthetic html/md/txt/pdf + generator
```

Every one declares `SYNTHETIC TEST FIXTURE - NOT A REAL NOTICE` on line 1.

## Recorded transport fixtures

```text
tests/fixtures/grants_gov/nf_seed_2026_fed_021_samhsa_sm_26_024.json   1
```

Exactly one recording, for seed `nf-seed-2026-fed-021`. It is the only path by
which anything resembling a real Grants.gov response enters the suite, and it is
opt-in via `load_recorded_transport`.

## Source seed catalogs

Three catalogs, not one. A first pass at this survey counted only two and
missed 14 seeds; the corrected enumeration is:

```text
source_seed_catalog.FEDERAL_SEEDS           4    has source_url
source_seed_catalog.SOUTH_CAROLINA_SEEDS    4    has source_url
source_seed_catalog.EXPANSION_SEEDS         6    has source_url
sc_source_seed_catalog.SC_SEEDS             7    NO url field
federal_source_seed_catalog.FEDERAL_SEEDS   6    has url
                                           --
                                           27 entries before dedupe by catalog_key
source_seed_catalog.LANES  (federal,south_carolina,expansion)
```

`source_seed_catalog` uses `catalog_key / source_url / source_type /
jurisdiction / access_method`; the two later catalogs use `catalog_key / lane /
family / scope / rationale`. Baseline X normalises both shapes onto
`source_registry_service.build_source_record` rather than inventing a third.

`sc_source_seed_catalog.SC_SEEDS` carries no `url` field at all. That is
deliberate from Gate 78: SC has no central grants portal and no source was
terms-cleared, so seeding a URL would have implied a monitorable source that
does not exist. Those 7 seeds are not monitorable, and Baseline X counts them
that way rather than rounding them up.

`federal_source_seed_catalog.FEDERAL_SEEDS` does carry `url`, `agency`,
`access_method`, `native_expected`.

**No catalog carries a monitoring flag.** There is no
`monitoring_enabled`, `terms_reviewed` or `robots_reviewed` field on any seed.
So `monitored_sources = 0` is provable from the committed data rather than
asserted.

## Machinery to reuse — never fork

| Concern | Service | What Baseline X takes from it |
| --- | --- | --- |
| opportunity quality score | `opportunity_discovery_quality_service` | `build_discovery_quality_score`, `build_source_coverage_baseline`, weights |
| discovery record shape | `native_opportunity_discovery_service` | `build_native_opportunity_record`, `LANES` |
| canonical funding lanes | `opportunity_funding_lane_service` | `FUNDING_LANES` (8), `discovery_lane`, `sc_routing_lane` |
| eligibility / exclusion | `eligibility_exclusion_evidence_service` | `APPLICANT_CLASSES` (8), `RESULT_STATES` (6), `evaluate_all_applicant_classes` |
| notice parsing | `nofo_text_extraction_service`, `nofo_eligibility_parser_service` | extraction + per-class cited verdicts |
| amendment status | `nofo_amendment_detector_service` | `NOTICE_STATUSES` (9), freshness projection |
| ingestion | `notice_ingestion_pipeline_service` | artifact → cited eligibility, end to end |
| freshness | `opportunity_freshness_service` | `FRESHNESS_STATES` (6), `CURRENT_STATES` |
| source registry | `source_registry_service` | `PROMOTION_STATUSES`, `MONITORING_STATUSES`, `ROBOTS_TERMS_CLEARED`, `RETIREMENT_STATUSES` |
| lanes by jurisdiction | `sc_state_source_lane_service`, `federal_source_lane_service` | family/scope vocabularies |
| determinism | `demo_payload_determinism_service` | fixed clock + seeded identity for artifact writing |

**Vocabulary rule, carried from Gate 79B:** Baseline X declares no new lane,
applicant class, freshness state or result state. Every metric key is drawn from
an existing frozenset, and a drift test pins that.

## Provenance split as it stands

```text
synthetic   the Gate 81/82 notice fixtures, stage12 demo path, curated demo packs
recorded    the real_grants_corpus family, the single grants_gov transport
live        NONE - 0 records, 0 sources monitored, 0 notices fetched
unverified  the Gate 78R SC eligibility strings (eligibility_verified: false)
```

## What Baseline X must not do

- No live fetch, no URL resolution, no scraping.
- No fixture mutation — asserted by hashing watched fixtures before and after.
- No new opportunity, eligibility, ineligibility or freshness value invented.
- No relevance-to-eligibility conversion.
- No collapsing of `state_recognized_tribe` and `federally_recognized_tribe`.
- No hiding of excluded opportunities — they are counted as negative
  intelligence and stay visible.
- No improvement claim. `improvement_claim_allowed` is hardcoded false.

## Gap this baseline exists to expose

The campaign has built the machinery to classify lanes, cite exclusions, parse
notices and ingest documents — and has applied almost none of it to the corpus
at scale. Baseline X is the first measurement of how much of the 168-record
corpus that machinery can actually say something evidence-backed about.
