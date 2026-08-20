# Campaign Block 08 — Sunday / Monday Demo Checkpoint (111)

## Route

`/?view=sc_customer_demo`

## Startup

```bash
cd /home/josefgray/projects/nativeforge
source .venv/bin/activate
bash scripts/nofo_showcase_regen_bridge.sh
cd frontend && npm run dev
```

## Allowed claims

- Fixture-backed organization evidence memory for SC pilot profiles
- Recognition tier/status kept distinct (federal vs state_only)
- Missing UEI/SAM, population, prior awards, governance, resolutions shown honestly
- Memory feeds eligibility / binder / checklist / readiness gap visibility
- No auto-approved facts without evidence/review

## Forbidden claims

- Final eligibility
- Customer data persistence / durable customer mutation
- Binary upload persistence
- Live ingest / source activation
- Fabricated tribal history, population, awards, resolutions, partners
- Treating state recognition as federal

## Smoke

- `bash scripts/campaign_block08_smoke_verify.sh`
- `bash scripts/campaign_block07_smoke_verify.sh` (Gate 01 regression)
- Playwright: `cd frontend && npm run test:e2e:sc-monday-smoke`
