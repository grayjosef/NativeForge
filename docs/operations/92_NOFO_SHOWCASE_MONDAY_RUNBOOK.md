# NOFO Showcase Monday Demo Runbook

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

## Route

`/?view=sc_customer_demo`

## Demo sequence

1. Open SC customer demo route.
2. Show curated SC + federal opportunity queue (existing Monday lane).
3. Scroll to **NOFO / synopsis intelligence + application plan skeleton**.
4. Open the SC Food Sovereignty card — show known vs missing field statuses.
5. Open a federal card (ANA SEDS or TEDC) — same honesty labels.
6. Walk buyer sections: What NativeForge found → means → missing → human review → next.
7. Show application checklist + missing-information questions (no invented answers).
8. Explicitly state limitations: no full NOFO PDF extraction; no proposal drafting.

## Claims allowed

- Curated-current / synopsis intelligence for selected opportunities
- Honest field statuses (`known` / `inferred` / `missing` / `needs_confirmation` / `not_in_source` / `not_supported`)
- Application plan skeleton + checklist
- Human review required while evidence incomplete
- Live ingest not claimed

## Claims forbidden

- Full live NOFO PDF extraction
- Automated proposal narrative writing
- Fabricated tribal facts, budgets, resolutions, past performance, partnerships
- Final eligibility without human evidence review
- Live source activation / production mutation

## Fallback

```bash
bash scripts/nofo_showcase_smoke_verify.sh
bash scripts/sc_monday_demo_staging_verify.sh
```

If UI unavailable, show `fixtures/nofo_showcase/selected_opportunity_intelligence_pack.json` and application plans JSON offline.
