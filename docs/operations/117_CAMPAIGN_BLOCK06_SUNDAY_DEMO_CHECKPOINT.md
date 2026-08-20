# Sunday / Monday Demo Checkpoint — Campaign Block 06

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

- Narrative & budget scaffold panel
- Likely/required narrative sections with known vs missing evidence
- Missing narrative questions (no invented answers)
- Budget/match evidence status without fabricated amounts
- Drafting not supported / no generated prose honesty

## Allowed claims

- Narrative section scaffolds from intelligence/checklist/binder
- Missing facts become questions, not prose
- Budget/match evidence capture with completeness guards
- Proposal drafting not supported in this layer

## Forbidden claims

- Generated proposal prose
- Fabricated budget/match amounts
- Budget or match completeness without evidence
- Auto-submit / submission-ready
- Live ingest / scoring changes

## Run_ids (Block 06 closeout)

- Offline Block 06: `nf_camp06_narrative_smoke_20260820T181232Z_968b5e6d`
- Demo-runtime: `nf_sc_monday_browser_20260820T181234Z_b2d10aa0`
- Playwright: `nf_sc_monday_playwright_20260820T181236Z_6b909412`
- Staging digest: `0952cc002f8ed139`

## Checkpoint

Sunday/Monday checkpoint **109** (Campaign Block 06).

## Fallback

```bash
bash scripts/campaign_block06_smoke_verify.sh
bash scripts/sc_monday_demo_staging_verify.sh
bash scripts/sc_monday_demo_runtime_smoke_verify.sh
bash scripts/sc_monday_playwright_e2e_smoke_verify.sh
```
