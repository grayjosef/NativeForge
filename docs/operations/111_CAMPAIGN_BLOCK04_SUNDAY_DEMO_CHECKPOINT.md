# Sunday / Monday Demo Checkpoint — Campaign Block 04

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

- Application checklist / package build plan section
- Checklist sections + item status
- Missing-information questions (no invented answers)
- What NativeForge knows vs customer must provide
- Why submission is not allowed
- Unsupported proposal/PDF/submit claims

## Allowed claims

- Executable checklist from binder + plan + intelligence
- Evidence-backed missing-information questions
- Human review gates remain explicit
- Submission not allowed without complete package + human review

## Forbidden claims

- Proposal drafting / fabricated narrative
- Application complete / submission-ready
- Auto-submit
- Fabricated NOFO requirements
- Automated NOFO PDF extraction
- Live ingest / scoring changes

## Run_ids (Block 04 closeout)

- Offline Block 04: `nf_camp04_checklist_smoke_20260820T175035Z_d78bc817`
- Demo-runtime: `nf_sc_monday_browser_20260820T175037Z_de58bd43`
- Playwright: `nf_sc_monday_playwright_20260820T175040Z_d8d53610`
- Staging digest: `0952cc002f8ed139`

## Checkpoint

Sunday/Monday checkpoint **107** (Campaign Block 04).

## Fallback

```bash
bash scripts/campaign_block04_smoke_verify.sh
bash scripts/sc_monday_demo_staging_verify.sh
bash scripts/sc_monday_demo_runtime_smoke_verify.sh
bash scripts/sc_monday_playwright_e2e_smoke_verify.sh
```
