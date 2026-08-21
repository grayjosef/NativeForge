# Monday Buyer Demo Runbook — SC Customer Story

## Startup

```bash
cd /home/josefgray/projects/nativeforge
source .venv/bin/activate
bash scripts/nofo_showcase_regen_bridge.sh
# Terminal A
uvicorn nativeforge.main:app --reload
# Terminal B
cd frontend && npm run dev
```

Open: `/?view=sc_customer_demo`

## Exact opening line

> NativeForge structures South Carolina and federal grant opportunities for your organization — curated-current intelligence, honest gaps, and an application-plan skeleton — without fabricating live ingest, NOFO PDFs, or proposal prose.

## Demo sequence (talk track)

1. **Opening** — Read the opening line. Point at trust strip: curated-current, not live ingest, human review.
2. **Organization context** — SC profiles (10), federal vs state_only recognition.
3. **SC + federal opportunities** — One queue; call out geography columns.
4. **Uncertainty** — Missing data / attention list; no silent fills.
5. **Pick an opportunity** — Scroll to NOFO/synopsis intelligence.
6. **SC card** — Food Sovereignty: known vs missing vs not_supported.
7. **Federal card** — ANA SEDS or TEDC: same honesty labels.
8. **Application-plan skeleton** — Checklist + missing-info questions (no invented answers).
9. **Claim guardrails** — Show Allowed vs Forbidden lists on page.
10. **Close** — Read closing line.

## Exact closing line

> Next step: human review of missing evidence and active rounds, then decide pursue or defer — NativeForge will not submit or invent facts for you.

## What to say about…

| Topic | Say |
|-------|-----|
| Curated-current | Operator-curated pack with capture date; not a live feed |
| Live ingest | Not claimed; no portal scraping in this demo |
| NOFO/PDF | Synopsis/curated intelligence only; full PDF extraction not supported yet |
| Proposal drafting | Not supported; skeleton checklist only |
| Eligibility | Evidence + blockers + needs confirmation; no final claim |
| Human review | Required before pursue/submit |
| Security / sovereignty | Evidence and isolation labels visible; do not claim pen-test, production auth, or full sovereignty deployment |

## Fallbacks

- Frontend fails: `bash scripts/sc_monday_demo_staging_verify.sh` + show fixtures under `fixtures/nofo_showcase/`
- Playwright fails: `bash scripts/monday_buyer_demo_smoke_verify.sh` + offline smoke artifacts
- Bridge stale: `bash scripts/nofo_showcase_regen_bridge.sh`

## Claims allowed / forbidden

See on-page guardrails and `docs/operations/100_MONDAY_BUYER_CLAIM_MATRIX.md`.

## Campaign Block 01 note

Durable opportunity engine foundation is on the same route (`opportunity_engine` panel).
Monday-safe claims/fallbacks: `docs/operations/102_CAMPAIGN_BLOCK01_SUNDAY_DEMO_CHECKPOINT.md`.

## Campaign Block 02 note

Evidence-backed eligibility + recognition-tier explanations are on the same route.
See `docs/operations/105_CAMPAIGN_BLOCK02_SUNDAY_DEMO_CHECKPOINT.md`.

## Gate 07–08 operator notes

### Additional panels on `/?view=sc_customer_demo`

- Multi-organization pilot / cohort readiness
- Future collaboration / dark launch (OFF)
- Evidence intake / uploads (fixture/planned — persistence not claimed)
- Operator enablement / production readiness (go/no-go)

### Operator commands

```bash
source .venv/bin/activate
bash scripts/sc_monday_demo_staging_verify.sh
bash scripts/campaign_block21_smoke_verify.sh
bash scripts/campaign_block22_smoke_verify.sh
bash scripts/sc_monday_playwright_e2e_smoke_verify.sh
```

### Monday-safe claim boundaries (Gate 08)

Allowed: evidence intake contract; storage proposal; operator go/no-go; Monday demo GO.

Forbidden: uploads stored/durable; production-ready; pen-test passed; customer login live; submission-ready; final export; collaboration matching.

Storage proposal: `docs/operations/161_EVIDENCE_UPLOAD_STORAGE_PROPOSAL.md` (migrations not applied).

## Gate 09–10 operator notes

### Additional panels

- Persistent storage approval / local/dev validated persistence
- Customer pilot auth scaffolding (login not live)
- Gate 10 closeout / pen-test readiness

### Monday story (Gate 10)

NativeForge is a Native-specific grant pursuit operating system with evidence-backed
eligibility, source intelligence, package assembly, controlled drafting, deterministic
QA, feedback reporting, multi-org cohort view, **local/dev validated evidence
persistence**, and honest no-go boundaries for production/customer rollout.

### Operator commands (Gate 10)

```bash
source .venv/bin/activate
bash scripts/campaign_block25_smoke_verify.sh
bash scripts/campaign_block26_smoke_verify.sh
bash scripts/nofo_showcase_regen_bridge.sh
# frontend e2e
cd frontend && npm run test:e2e -- e2e/sc_customer_demo.smoke.spec.ts
```

### Monday-safe claim boundaries (Gate 10)

Allowed: Monday demo GO; local/dev validated persistent evidence storage; external
pilot auth path scoped; pen-test/SCA readiness packets complete.

Forbidden: production storage; customer data persistence; customer login live;
production auth/multi-tenant; pen-test passed; SCA passed (unless tooling green);
controlled customer pilot GO; submission-ready; final export; collaboration live.

Applied storage record: `docs/operations/172_LOCAL_DEV_PERSISTENT_STORAGE_APPLIED.md`
