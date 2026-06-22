# NativeForge Handoff — Block NF-14: Mixed-Corpus Classifier Discrimination (Sprints 332–339)

**Status:** Complete (local). **WAIT** — do not push unless explicitly approved.

## Summary

Built a mixed real corpus (40 NF-13 tribal federal grants + 17 recorded Grants.gov broad/edge/label-spread pulls) and classified the full set through the Stage 6 native-relevance classifier. Stressed overclaim and over-filter guards; added a new tribe-eligible-broad discoverability guard that fails when a tribe-eligible broad grant is dropped to `irrelevant`. Re-examined NF-13's two `irrelevant` grants — both are corpus-artifact mislabels (placeholder eligibility), not classifier over-filter.

## Mixed corpus

| Segment | Count | Source |
|---------|-------|--------|
| `tribal_federal` | 40 | `nf13_real_ingested_grants.json` |
| `broad` | 7 | Grants.gov live pulls (SBIR, INFRA, DOT, NSF, FHWA, …) |
| `edge` | 4 | Tribes among many eligible applicant types |
| `label_spread` | 6 | Additional live pulls for label discrimination |

**Fixture:** `fixtures/real_grants_corpus/nf14_mixed_corpus.json` (57 grants)  
**Recorded pulls:** `fixtures/real_grants_corpus/nf14_grants_gov_broad_edge_pulls.json`  
**CI labeling:** supplemental grants `fixture: true`, `real_fetch: false`, `recorded_from_live_pull: true`

## Label distribution (57-grant mixed corpus)

| Label | Count |
|-------|------:|
| `tribal_government_specific` | 43 |
| `irrelevant` | 8 |
| `uncertain_relevance` | 2 |
| `native_entity_eligible_broad` | 1 |
| `weak_native_relevance` | 2 |
| `native_specific` | 1 |

**Not in live mixed distribution** (covered by vocabulary discrimination anchors in worked examples): `indigenous_community_relevant`, `broadly_eligible_potentially_relevant`.

## Tribe-eligible broad discoverability

- **8** grants flagged `tribe_eligible_broad` (unrestricted eligibility or tribal among multi-type applicant lists)
- **8/8** remained discoverable (not `irrelevant`)
- Guard: `tribe_eligible_broad_discoverability_guard_service.py` — test fails if tribe-eligible broad → `irrelevant`

## NF-13 irrelevant re-examination

| Grant | Title | Verdict |
|-------|-------|---------|
| `nf13-real-fed-021` | AI/AN Zero Suicide & Suicide Prevention | Corpus artifact — generic placeholder eligibility, no tribal flags in payload |
| `nf13-real-fed-025` | General Assistance Program (GAP) | Corpus artifact — same pattern |

Both programs are tribally relevant by title/agency context, but the classifier correctly requires source-evidence fields; this is **not** over-filter.

## Guards exercised

- **Overclaim:** `native_specific` requires set-aside phrase in source (e.g. NTIA Native Entities synopsis: "set aside funds for Indian Tribes")
- **Over-filter:** tribe-eligible broad grants must stay discoverable; new invariant test in `test_sprint335_tribe_eligible_broad_guard.py`

## Routes

`POST .../mixed-corpus-discrimination` (demo + real org routers, plan-gated query flags)

## Gate / closeout

- `verify_mixed_corpus_discrimination_gates()` — 8 worked examples (one per label)
- `build_mixed_corpus_discrimination_closeout_packet()`

## Test baseline

Run: `ruff check . && pytest` — expect green after NF-14.

## Governance

- Staging only (`NF_APP_ENV=staging`, plan approval env vars)
- **Never pushed** in this block
- `stash@{0}` preserved
