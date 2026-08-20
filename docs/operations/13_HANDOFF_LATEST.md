# 13_HANDOFF_LATEST — NativeForge

## Campaign Block complete

**Block 1 of 20 — NF Campaign Block 01 — Durable SC + Federal Opportunity Engine Foundation**

## Control point

- path: `/home/josefgray/projects/nativeforge` (stale clone avoided)
- branch: `main`
- HEAD before: `4f5e166`
- HEAD after: `40010a4`
- protected stash: `stash@{0}: On main: wip-sprint8-ui-redesign-do-not-commit`
- uv.lock: present, untouched

## Durable software delivered

- Opportunity engine contracts (`source_layer`, `data_mode`, health, freshness, lifecycle, eligibility handoff)
- SC reference-state adapter/config (`state_portal_sc_curated`) — not a product fork
- Federal foundation enricher for SC customers (org geo ≠ funding geo)
- Combined opportunity workflow service (deterministic SC-then-federal ordering)
- Product surface on `/?view=sc_customer_demo` via `opportunity_engine` bridge payload
- Sunday/Monday demo checkpoint: `docs/operations/102_CAMPAIGN_BLOCK01_SUNDAY_DEMO_CHECKPOINT.md`

## Smoke run_ids

- Block 01 offline: `nf_camp01_engine_smoke_20260820T171835Z_09ea0e8d`
- Demo-runtime: `nf_sc_monday_browser_20260820T171738Z_558ae376`
- Playwright: `nf_sc_monday_playwright_20260820T171847Z_58e3fd4b`

## NEXT SAFE ACTION

Campaign Block 02 — recommended: Evidence-backed eligibility + recognition-tier productization (still no live ingest), or approved NOFO PDF extraction pilot for one showcase opportunity.
