# Campaign Block 10 — Sunday / Monday Demo Checkpoint (113)

## Route

`/?view=sc_customer_demo` → **Source freshness / source health**

## Allowed

- Read-only / fixture-backed freshness pilot
- Distinguishes curated-current, fixture, unsupported portal
- Deadline and staleness risk labels
- Operator next-check guidance

## Forbidden

- Full live ingestion
- Continuous production monitoring
- Source activation complete
- Freshness proves eligibility

## Smoke

`bash scripts/campaign_block10_smoke_verify.sh`
