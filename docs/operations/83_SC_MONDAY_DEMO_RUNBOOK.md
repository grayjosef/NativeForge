# SC Monday Demo Runbook (Sprint 042)

## Start

```bash
cd /home/josefgray/projects/nativeforge
source .venv/bin/activate
# optional staging verify
bash scripts/sc_monday_demo_staging_verify.sh
cd frontend && npm run dev
# open http://127.0.0.1:5173/?view=sc_customer_demo
```

## Honest claims

- Curated/fixture opportunities only — **not** automated live ingestion
- No source activation
- No final eligibility claim
- Human review required

## Validation

- `bash scripts/sc_monday_demo_smoke_verify.sh`
- `bash scripts/sc_monday_playwright_e2e_smoke_verify.sh`

## Run ids (this block)

- offline smoke (closeout): `nf_sc_monday_smoke_20260820T151221Z_f29132e0`
- Playwright: `nf_sc_monday_playwright_20260820T151118Z_009c45c6`
