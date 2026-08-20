# 13_HANDOFF_LATEST — NativeForge

## Block complete

**NF SC Monday Demo Lane — Curated-Current Opportunities + Guided Customer Story**

## Control point

- path: `/home/josefgray/projects/nativeforge` (stale clone `/home/josefgray/projects/NativeForge` avoided)
- branch: `main`
- HEAD before: `7e62fbf`
- HEAD after: `1fc4b89` (confirm with git rev-parse)
- origin/main: local ahead (**not pushed**)
- working tree: clean at block stop (ignore untracked prior Playwright debris if any)
- protected stash: `stash@{0}: On main: wip-sprint8-ui-redesign-do-not-commit`
- uv.lock: present, untouched/unstaged
- prior block: NF Full-Suite Health / Lint-Debt Containment Block

## Monday demo lane

- route: `/?view=sc_customer_demo`
- curated pack: `fixtures/sc_monday_demo/sc_curated_current_opportunity_pack.json`
- profiles: 10 SC pilot fixtures
- opportunities: 18 (3 SC + 15 federal), honestly labeled
- live_ingestion claimed: **no**
- source_activation: **no**
- final eligibility claim: **not allowed**
- offline smoke: PASS `nf_sc_monday_smoke_20260820T151221Z_f29132e0`
- Playwright: PASS `nf_sc_monday_playwright_20260820T151118Z_009c45c6`

## Validation

- staging verify: OK
- scoped pytest: PASS
- frontend typecheck: PASS
- Playwright E2E: PASS
- full suite: NOT_RUN this block
- repo-wide ruff autofix: not used

## Safety

- scoring/match math unchanged (recognition-tier gate reused only)
- no migrations
- no live ingest / activation
- stash preserved
- pushed: **no**

## UNKNOWNs

- Freshness of curated opportunities vs true live portal rounds (confirm_active_round required)
- Which of the four SC prospect orgs map 1:1 onto fixture keys for live demos

## NEXT SAFE ACTION

Continue campaign block 2 (federal curated-current completeness) or NOFO extraction showcase. Mayhem push when ready.
