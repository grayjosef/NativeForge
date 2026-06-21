# NativeForge Handoff — Block NF-12: Lock Live Pull + Scale Tier-1 Activation (Sprints 313–321)

**Date:** 2026-05-19  
**Branch:** `main` (ahead of `origin/main`)  
**Push:** Not performed (per governance)  
**Stash:** Preserved — `stash@{0}: wip-sprint8-ui-redesign-do-not-commit`

## Run summary

Completed NF-12 with green baseline. Locked honest `real_fetch` labeling with a fail-closed invariant guard and tests that fail on violation. Fixed 49 catalog URL path mismatches (prior 48 dead). Scaled tier-1 federal activation in a controlled public batch with live Grants.gov fetch, idempotent dedupe, and honest empty NOFO reporting.

| Sprint | Summary |
|--------|---------|
| 313 | `real_fetch_honest_labeling_guard_service` — fixture can never carry `real_fetch: true` |
| 314 | Eligibility parser hardened — applicantTypes 07/11 + TEDC verification |
| 315 | Seed URL corrections (49 rows) + corrected posture report |
| 316 | Batch tier-1 public federal human activation gate |
| 317 | Batch live Grants.gov fetch + canonical-id dedupe |
| 318 | `tier1-batch-live-pull` orchestrator — STOP at checkpoint |
| 319–320 | Gate verification + closeout packet |
| 321 | Block closeout |

## Honest labeling (locked)

- `assert_real_fetch_honest_labeling()` enforced on every Grants.gov payload at parse time.
- **Invariant:** `real_fetch: true` ONLY when `fetch_mode: live` AND `search_live` AND `detail_live` are all true.
- Fixtures/replays: `fixture: true`, `real_fetch: false` — guard raises if violated.
- Tests **fail** if a fixture payload carries `real_fetch: true` (`test_sprint313`).

## URL corrections

| Metric | Before | After (CI mock) |
|--------|--------|-----------------|
| Dead catalog URLs | 48 | 0 (mock resolver) |
| Corrected seed rows | — | 49 |
| Notable fixes | ACL title-vi 404, EPA GAP path, IMLS fed-050 on BIA domain, First Peoples Fund paths |

Corrections applied in CSV and at load time via `source_seed_url_correction_service`.

## Batch tier-1 activation

- **Route:** `POST .../tier1-batch-live-pull?nf_live_source_ingestion=true&nf_real_resolver_validation=true`
- **Confirmation:** `operator_handle`, `human_activation_acknowledged`, `public_only_acknowledged`, `batch_tier1_public_activation_acknowledged`
- Activates all green public tier-1 federal sources (CI gate uses `max_batch_size=8`)
- Live `search2` + `fetchOpportunity` per source; empty when no ALN-matched NOFO
- **Report fields:** `sources_activated`, `real_grants_ingested` (`real_fetch` proven live), `empty_nofo_sources`, corrected posture

## Eligibility parser

TEDC record (`grants_gov_fetch_opportunity_362648.json`):
- `tribal_eligible: true` (applicantTypes 07/11 + narrative)
- `eligibility_text` populated with applicant types + `applicantEligibilityDesc`

## Build / test state

- **Baseline at block start:** `5129 passed`, `11 skipped`
- **Full pytest (final):** `5138 passed`, `11 skipped` (+9 tests)
- **Stash:** Untouched

## Hard invariants preserved

- Staging only; same plan gates as NF-9/NF-11
- Public-only batch activation; no CAPTCHA/login bypass; no credentials
- Never synthesize NOFOs
- **STOP** at checkpoint — no push
- **WAIT**

## Proposed next safe action

1. Deploy to staging; POST `tier1-batch-live-pull` for full 60-source batch with live HTTP.
2. Review `real_grants_ingested` vs `empty_nofo_sources` per program ALN.
3. Do not push without Mayhem review.

## Verification commands

```bash
cd /home/josefgray/projects/nativeforge
pytest -q
pytest tests/test_sprint313_real_fetch_honest_labeling_guard.py tests/test_sprint315_seed_url_correction.py tests/test_sprint320_tier1_batch_live_pull_closeout.py -q
```
