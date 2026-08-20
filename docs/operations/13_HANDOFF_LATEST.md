# 13_HANDOFF_LATEST — NativeForge

## Block complete

**NF SC Monday Demo Lane — Curated-Current Opportunities + Guided Customer Story**

## Control point

- path: `/home/josefgray/projects/nativeforge` (stale clone `/home/josefgray/projects/NativeForge` avoided)
- branch: `main`
- HEAD before: `7e62fbf`
- HEAD after: `297727c` (confirm with git rev-parse)
- origin/main: local ahead (**not pushed**)
- protected stash: `stash@{0}: On main: wip-sprint8-ui-redesign-do-not-commit`
- uv.lock: present, untouched/unstaged

## Monday demo lane

- route: `/?view=sc_customer_demo`
- curated pack: `fixtures/sc_monday_demo/sc_curated_current_opportunity_pack.json` (+ SC/federal split packs)
- GO data contract: `sc_monday_go_contract_service` (live_ingest_claimed=false, automated_refresh_claimed=false)
- profiles: 10 SC pilot fixtures
- opportunities: 18 (3 SC + 15 federal)
- offline smoke: PASS `nf_sc_monday_smoke_20260820T161217Z_53533b08`
- demo-runtime smoke: PASS `nf_sc_monday_browser_20260820T161227Z_8e58492b`
- Playwright: PASS `nf_sc_monday_playwright_20260820T161253Z_5c1c16cc`
- NOFO PDF extraction: NOT_IN_THIS_BLOCK
- proposal drafting: NOT_IN_THIS_BLOCK

## NEXT SAFE ACTION

Campaign block 2 (federal curated completeness) or NOFO extraction showcase. Mayhem push when ready.
