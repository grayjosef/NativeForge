# NOFO Showcase — Validation Matrix

| Check | Status | Evidence |
|-------|--------|----------|
| Field status contract tests | PASS | `tests/test_nofo_showcase_field_status.py` |
| Intelligence + plan tests | PASS | `tests/test_nofo_showcase_intelligence_and_plan.py` |
| Surface + offline smoke tests | PASS | `tests/test_nofo_showcase_surface_and_smoke.py` |
| Staging verify | PASS | `scripts/sc_monday_demo_staging_verify.sh` |
| Offline NOFO smoke | PASS | `nf_nofo_showcase_smoke_*` |
| Demo-runtime vitest | PASS | `nf_sc_monday_browser_*` |
| Playwright SC demo + NOFO | PASS | `nf_sc_monday_playwright_*` |
| Frontend typecheck/build | PASS | `npm run typecheck` / `npm run build` |

## Honesty

- `live_ingest_claimed=false`
- `nofo_pdf_extraction_claimed=false`
- `proposal_drafting_claimed=false`
- Human review required on all showcase cards
