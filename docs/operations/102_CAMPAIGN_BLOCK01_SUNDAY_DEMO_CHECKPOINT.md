# Sunday / Monday Demo-Adjustment Checkpoint — Campaign Block 01

**Date context:** Campaign Block 01 closeout (durable opportunity engine foundation).
Monday is a checkpoint, not the ceiling.

## Current demo route

`/?view=sc_customer_demo`

## Startup command

```bash
cd /home/josefgray/projects/nativeforge
source .venv/bin/activate
bash scripts/nofo_showcase_regen_bridge.sh
# Terminal A
uvicorn nativeforge.main:app --reload
# Terminal B
cd frontend && npm run dev
```

## What is safe to show Monday

- SC organization profiles + curated SC state opportunities
- Federal opportunities in the same workflow (org geography does not hide federal)
- Durable opportunity engine foundation panel (reference-state adapter + combined counts)
- Honest curated-current / not live ingest labels
- NOFO/synopsis intelligence + application-plan skeleton (selected showcase)
- Human review, missing fields, provenance, claim guardrails
- Opening + closing buyer lines

## Allowed claims

- Curated-current SC + federal opportunity spine
- SC is reference-state adapter/config (not a product fork)
- Combined workflow with provenance, freshness, lifecycle, eligibility handoff
- Missing data remains visible; human review required
- Material reduction of discovery/pursuit prep workload
- Application-plan skeleton (not a finished proposal)

## Forbidden claims

- Automated live ingestion / source activation
- Full NOFO PDF extraction
- Proposal drafting
- Final eligibility without human evidence review
- Nationwide live state coverage beyond SC reference config
- Production auth / pen-test / full sovereignty deployment

## Latest run_id(s)

- Block 01 offline: `nf_camp01_engine_smoke_20260820T171835Z_09ea0e8d`
- Demo-runtime: `nf_sc_monday_browser_20260820T171738Z_558ae376`
- Playwright: `nf_sc_monday_playwright_20260820T171847Z_58e3fd4b`

## Fallback path

```bash
bash scripts/campaign_block01_smoke_verify.sh
bash scripts/sc_monday_demo_staging_verify.sh
bash scripts/monday_buyer_demo_smoke_verify.sh
```

If UI fails: show `fixtures/opportunity_engine/sc_state_source_adapter_config.json` and combined workflow via Python REPL from `build_combined_opportunity_workflow()`.

## Blockers

- Live SC portal ingest: not implemented (blocked pending approval)
- Live federal ingest: not claimed
- Full NOFO PDF extraction / proposal drafting: not supported

## Continue rule

Continue campaign Block 02 only after Mayhem reviews this checkpoint if demo readiness is the priority that day.
