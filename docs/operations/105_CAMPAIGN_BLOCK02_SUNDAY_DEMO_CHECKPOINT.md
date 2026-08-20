# Sunday / Monday Demo Checkpoint — Campaign Block 02

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

- Evidence-backed eligibility panel (applicant category, recognition tier, missing evidence, next checks)
- Federal vs state recognition kept separate
- SC + federal opportunities together
- Final eligibility not claimed
- Scoring math unchanged

## Allowed claims

- Evidence-backed eligibility explanations on curated-current opportunities
- Recognition-tier gate reused (productized explanations)
- Missing evidence visible; human review required
- Federal opportunities remain discoverable for SC orgs

## Forbidden claims

- Final eligibility determination
- Live ingest / source activation
- Scoring math changes
- Treating state-recognized as federally recognized
- Full NOFO PDF extraction / proposal drafting

## Run_ids

- Block 02 offline: `nf_camp02_eligibility_smoke_20260820T172530Z_243119cd`
- Demo-runtime: `nf_sc_monday_browser_20260820T172532Z_c47f0c88`
- Playwright: `nf_sc_monday_playwright_20260820T172534Z_db8a7abc`

## Fallback

```bash
bash scripts/campaign_block02_smoke_verify.sh
bash scripts/sc_monday_demo_staging_verify.sh
```

## Blockers

Live eligibility from live portals; legal final determinations; pen-test/auth overclaims.
