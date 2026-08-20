# Sunday / Monday Demo Checkpoint — Campaign Block 07

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

- Readiness & review queue panel
- Overall + per-layer readiness
- Blockers, missing info, human review, unsupported counts
- Operator review queue with critical-first priorities
- Next safest action
- Explicit not-submission-ready / no final eligibility / no drafting / no live ingest

## Allowed claims

- Package readiness rollup across workflow layers
- Operator review queue prioritizing blockers
- Unsupported capabilities remain visible
- Next safest action is human review — not drafting or submission

## Forbidden claims

- Submission-ready
- Final eligibility
- Proposal drafting / generated prose
- Live ingest
- Role assignment / auto-unlock

## Run_ids (Block 07 closeout)

- Offline Block 07: `nf_camp07_readiness_smoke_20260820T182540Z_cb0d8e62`
- Demo-runtime: `nf_sc_monday_browser_20260820T182543Z_1f20e73e`
- Playwright: `nf_sc_monday_playwright_20260820T182546Z_eace90bf`
- Staging digest: `0952cc002f8ed139`

## Checkpoint

Sunday/Monday checkpoint **110** (Campaign Block 07).

## Fallback

```bash
bash scripts/campaign_block07_smoke_verify.sh
bash scripts/sc_monday_demo_staging_verify.sh
bash scripts/sc_monday_demo_runtime_smoke_verify.sh
bash scripts/sc_monday_playwright_e2e_smoke_verify.sh
```
