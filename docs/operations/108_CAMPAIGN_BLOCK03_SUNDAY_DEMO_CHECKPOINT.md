# Sunday / Monday Demo Checkpoint — Campaign Block 03

## Route

`/?view=sc_customer_demo`

## Startup

```bash
cd /home/josefgray/projects/nativeforge
source .venv/bin/activate
bash scripts/nofo_showcase_regen_bridge.sh
uvicorn nativeforge.main:app --reload
# other terminal
cd frontend && npm run dev
```

## Safe to show

- Pursuit workspace / application package section
- Evidence binder counts + missing information
- Readiness never submission-ready; no submit control
- Linkage to eligibility + NOFO/synopsis + plan skeleton
- What NativeForge pre-built vs what customer must provide

## Allowed claims

- Structured pursuit workspace after opportunity selection
- Evidence binder with honesty statuses
- Deterministic next actions
- Not submission-ready without complete evidence + human review

## Forbidden claims

- Proposal drafting / fabricated narrative
- Final application / submission-ready
- Auto-submit
- Final eligibility without evidence
- Live ingest / scoring changes

## Run_ids (Block 03 closeout)

- Offline Block 03: `nf_camp03_pursuit_smoke_20260820T174103Z_a24dac10`
- Demo-runtime: `nf_sc_monday_browser_20260820T174126Z_9ba467d3`
- Playwright: `nf_sc_monday_playwright_20260820T174128Z_72e8f55c`
- Staging digest: `0952cc002f8ed139`

## Fallback

```bash
bash scripts/campaign_block03_smoke_verify.sh
bash scripts/sc_monday_demo_staging_verify.sh
bash scripts/sc_monday_demo_runtime_smoke_verify.sh
bash scripts/sc_monday_playwright_e2e_smoke_verify.sh
```

## Checkpoint

Sunday/Monday checkpoint **106** (Campaign Block 03).
