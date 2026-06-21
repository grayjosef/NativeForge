# NativeForge Handoff — Block NF-10: Real Seed + Real Grants.gov Fetch (Sprints 302–316)

**Date:** 2026-05-19  
**Branch:** `main` (ahead of `origin/main`)  
**Push:** Not performed (per governance)  
**Stash:** Preserved — `stash@{0}: wip-sprint8-ui-redesign-do-not-commit`

## Run summary

Completed NF-10 with green baseline (`5116` passed). Real seed CSV (177 rows, real URLs) loads via normalized 7-column format with fail-closed placeholder guard. Grants.gov `search2` + `fetchOpportunity` adapter replaces illustrative tier-1 fixtures. Re-runs real-resolver validation with corrected URL posture logic and recorded Grants.gov NOFO for CI.

| Sprint | Commit | Summary |
|--------|--------|---------|
| 302 | `47d073c` | Real seed URL guard + loader normalization for minimal CSV |
| 303 | `788c8f8` | URL resolver: dead vs login (403/404 no longer all dead) |
| 304 | `666e948` | Grants.gov search2 API adapter + recorded BIA-TEDC fixtures |
| 305 | `6c9357d` | Tier-1 live fetch via Grants.gov — empty if no match, never synthesize |
| 306 | `c5456b0` | NF-10 gate verification + closeout |
| 307 | `7d75040` | Tier-2 test aligned to real seed (51 state portals) |
| 308–316 | *(handoff)* | Block closeout |

## Real seed (`NF_SOURCE_SEED_2026.csv`)

| Metric | Value |
|--------|-------|
| Total rows | 177 |
| Tier 1 (federal) | 61 |
| Tier 2 (state) | 51 |
| Tier 3 (foundation/org) | 65 |
| Synthetic placeholder URLs | **0** (fail-closed guard) |

**fed-001:** `BIA / Interior — Aid to Tribal Governments (15.020)` → `https://www.bia.gov/topic/grants`

Loader accepts minimal 7-column real CSV and derives `source_type`, `publisher_name`, `program_family`, etc.

## Grants.gov adapter

- **search2:** `POST https://api.grants.gov/v1/api/search2` (no auth)
- **fetchOpportunity:** detail for matched hit
- **fed-001 search:** ALN `15.020` + `DOI-BIA` agency filter from source name
- **If no ALN-matched hit:** returns **empty list** — never synthesizes
- **CI fixture:** recorded `BIA-TEDC-2026` search hit (real API response shape)

## Real-resolver validation (re-run)

Same quadruple gate as NF-9. Corrected posture table replaces inflated dead counts (login/403 URLs no longer classified as dead). Baseline comparison vs synthetic hints (156/18/3) included in report.

## fed-001 activation + tier-1 fetch

- Exactly **one** source activated (`is_active=True`)
- Tier-1 fetch uses Grants.gov API in staging; recorded fixture in CI
- Idempotent canonical-id upsert: second run inserts 0
- **STOP** after fed-001 — no other activations

## Build / test state

- **Baseline at block start:** `5116 passed`, `11 skipped`
- **Full pytest (final):** `5124 passed`, `11 skipped` (+8 tests)
- **Ruff:** Green on NF-10 files
- **Stash:** Untouched

## Hard invariants preserved

- Staging only; same plan gates as NF-9
- No illustrative/synthetic NOFO fabrication
- No CAPTCHA/login bypass; no credentials
- Public-only activation path
- Exactly one active source (fed-001)

## Proposed next safe action

1. Deploy to staging; POST `real-resolver-validation` to get live posture counts vs 156/18/3 baseline.
2. Review Grants.gov empty result for ALN 15.020 if no posted NOFO — expected when program has no active listing.
3. Do not activate additional sources without separate authorization.

## Verification commands

```bash
cd /home/josefgray/projects/nativeforge
pytest -q
pytest tests/test_sprint302_real_seed_url_guard.py tests/test_sprint304_grants_gov_search_api_adapter.py tests/test_sprint306_real_seed_grants_gov_closeout.py -q
python -c "from nativeforge.services.source_ingestion_seed_loader_service import load_source_seed_rows; from nativeforge.services.source_seed_real_url_guard_service import assert_real_seed_urls; assert_real_seed_urls(load_source_seed_rows()); print('real seed OK')"
git stash list
```
