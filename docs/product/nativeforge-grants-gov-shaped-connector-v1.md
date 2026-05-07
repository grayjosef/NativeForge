# Grants.gov-shaped connector (v1, Sprint 26)

Offline mapping from Grants.gov-like JSON keys (fixtures, exports, shadow captures) into NativeForge connector candidates using existing normalization and native relevance scoring. **No live Grants.gov API calls.**

## Entry points

| Symbol | Role |
|--------|------|
| `grants_gov_like_to_fixture_row` / `normalize_grants_gov_payload` | Map one dict to internal row fields (title, agency, number, URL, CFDA, deadlines, synopsis, award amounts, category, funding instrument, inferred tribal signals). |
| `dry_run_grants_gov_shaped_rows` | Run `normalize_raw_dict` on each mapped row; provenance includes `fixture_connector: grants_gov_shaped`. |

## Field mapping (common aliases)

- **Title** → `opportunity_title` (`Title`, `OpportunityTitle`, …)
- **Agency** → `agency` (`agencyName`, `Agency`, …)
- **Number / id** → `opportunity_number` (`OpportunityNumber`, `opportunity_id`, …)
- **URL** → `source_url` (`OpportunityURL`, `url`, …)
- **CFDA** → `cfda_assistance_listing` (`CFDA`, `AssistanceListingNumber`, …)
- **Posted** → `posted_date` (`PostedDate`, …)
- **Close / deadline** → `application_deadline` (`CloseDate`, `SubmissionDeadline`, …)
- **Synopsis / description** → `description` + `raw_nofo_text`
- **Eligibility blocks** → concatenated for inference only (not the title)
- **Funding instrument** → `award_type` + optional `funding_instrument` (intake)
- **Category** → `program_category`
- **Award ceiling / floor** → `award_ceiling` / `award_floor` (numeric; optional in `build_normalized_fields`)

`opportunity_source_type` defaults to `federal` when omitted.

## Tribal inference (deterministic)

From synopsis + eligibility text only (excludes the title), phrase matches set `tribal_eligible` and tags such as `federally_recognized_tribe` and `tribal_government`. Explicit `tribal_eligible: true|false` in the payload wins and skips bool inference.

## Pipelines

- **Connector dry run:** `dry_run_grants_gov_shaped_rows` → `compute_duplicate_key` + `assess_native_relevance`.
- **Intake / source check:** map rows with `grants_gov_like_to_fixture_row`, then pass them to the existing `static_fixture_connector_intake_dry_run` or `run_source_check_backed_connector_dry_run` (same bridge as other offline fixtures; use pre-mapped rows).

## Fixtures

Sample exports live under `src/nativeforge/services/source_connectors/fixtures/grants_gov/` and are exercised in `tests/test_sprint26_grants_gov_fixture_connector.py`.
