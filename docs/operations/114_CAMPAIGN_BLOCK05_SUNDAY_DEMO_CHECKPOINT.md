# Sunday / Monday Demo Checkpoint — Campaign Block 05

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

- Intake & approvals / package gaps panel
- Specific intake requests linked to checklist/binder gaps
- Accepted evidence types + customer/operator actions
- Required reviewer roles + approval status (planned only)
- Why package is not ready
- Explicit no upload persistence / no approval persistence claims

## Allowed claims

- Planned intake requests from checklist + binder gaps
- Human approval workflow model (roles represented, not enforced)
- Package readiness remains locked without evidence + approval
- Binary upload and approval persistence not implemented

## Forbidden claims

- Uploaded files are stored
- Approvals are durably persisted
- Role/auth enforcement
- Proposal drafting
- Submission-ready / auto-submit
- Live ingest / scoring changes

## Run_ids (Block 05 closeout)

- Offline Block 05: `nf_camp05_intake_smoke_20260820T180004Z_21cf6b6f`
- Demo-runtime: `nf_sc_monday_browser_20260820T180034Z_c5e39b59`
- Playwright: `nf_sc_monday_playwright_20260820T180009Z_ade67595`
- Staging digest: `0952cc002f8ed139`

## Checkpoint

Sunday/Monday checkpoint **108** (Campaign Block 05).

## Fallback

```bash
bash scripts/campaign_block05_smoke_verify.sh
bash scripts/sc_monday_demo_staging_verify.sh
bash scripts/sc_monday_demo_runtime_smoke_verify.sh
bash scripts/sc_monday_playwright_e2e_smoke_verify.sh
```
