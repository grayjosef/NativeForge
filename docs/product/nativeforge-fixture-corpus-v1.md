# NativeForge fixture corpus (v1, Sprint 25)

Offline JSON bundles under `src/nativeforge/services/source_connectors/fixtures/corpus/` describe realistic opportunity shapes **before** any live scraping. They feed the existing static connector (`dry_run_fixture_rows`), intake bridge, connector manifest, and source-check-backed connector dry run — **no HTTP clients, no LLMs, no external APIs**.

## Loader

`fixture_corpus.py` discovers `*.json` bundles, expands Grants.gov-like aliases via `grants_gov_like_to_fixture_row`, attaches `fixture_category`, `fixture_key`, and `corpus_schema_version`, and exposes `load_all_corpus_rows_flat()` for tests and operators.

## Categories (expected relevance behavior)

| Category | Purpose | Expected scoring notes |
|----------|---------|-------------------------|
| `grants_gov_broad_tribal_eligible` | Grants.gov-shaped federal NOFO | Medium or higher from structured tribal eligibility without Native keywords in title/synopsis |
| `bia_tribal_specific` | BIA trust / transportation | **native_specific** via tribal set-aside |
| `ihs_tribal_health` | IHS health infrastructure | **high** — structured eligibility + tribal applicant pathway |
| `ana_language_culture` | ANA language / culture | **high** |
| `doe_indian_energy` | DOE Indian Energy | **high** — tribal priority + eligibility tags |
| `hud_onap_housing` | HUD ONAP / IHBG family | **high** |
| `epa_tribal_environment` | EPA tribal environmental capacity | **high** |
| `foundation_native_serving` | Philanthropic, Native-serving eligibility | **high** — nonprofit serving Native communities |
| `broad_rural_broadband_tribes_eligible` | Broad rural program with tribal governments eligible | Medium or higher without tribal/native tokens in title/synopsis blob |
| `irrelevant_broad_opportunity` | Generic STEM fellowship | **low** |
| `keyword_only_false_positive` | Title mentions tribal context; no structured tribal pathway | `review_required`, eligibility confidence not confirmed |
| `ambiguous_eligibility_case` | Block grant with unclear tribal applicability | `review_required`, ambiguous eligibility code |

Scoring uses `native_relevance.assess_native_relevance` unchanged.

## Why this stays no-network

Corpus data ships in-repo as JSON; the loader uses only `json`, `pathlib`, and existing normalization helpers. Operators and CI validate connector behavior deterministically without touching production sources.
