# 13_HANDOFF_LATEST — NativeForge

## Block complete

**NF NOFO Showcase Block — SC/Federal Opportunity Intelligence + Application Plan Skeleton**

## Control point

- path: `/home/josefgray/projects/nativeforge` (stale clone `/home/josefgray/projects/NativeForge` avoided)
- branch: `main`
- HEAD before: `89c99ef`
- HEAD after: (confirm with `git rev-parse --short HEAD` after push)
- origin/main: push authorized after green validation for this block
- protected stash: `stash@{0}: On main: wip-sprint8-ui-redesign-do-not-commit`
- uv.lock: present, untouched/unstaged

## Monday demo lane + NOFO showcase

- route: `/?view=sc_customer_demo`
- selected opportunities:
  - `sc-rule-SC_FOOD_SOVEREIGNTY` (SC)
  - `nf13-real-fed-012` (federal ANA SEDS)
  - `la-real-006` (federal TEDC)
- intelligence packs: `fixtures/nofo_showcase/`
- application plans: `fixtures/nofo_showcase/selected_opportunity_application_plans.json`
- offline NOFO smoke: PASS `nf_nofo_showcase_smoke_20260820T164133Z_8b3d9c41`
- demo-runtime smoke: PASS `nf_sc_monday_browser_20260820T164156Z_72917c42`
- Playwright: PASS `nf_sc_monday_playwright_20260820T164135Z_c0476cb2`
- SC Monday staging verify: OK
- NOFO PDF extraction: NOT_SUPPORTED (honest)
- proposal drafting: NOT_SUPPORTED (honest)
- live ingest claimed: false

## Runbook

See `docs/operations/92_NOFO_SHOWCASE_MONDAY_RUNBOOK.md`

## NEXT SAFE ACTION

Buyer-facing polish or real NOFO PDF extraction (only with approved source + validation). Mayhem may review push already completed for this block.
