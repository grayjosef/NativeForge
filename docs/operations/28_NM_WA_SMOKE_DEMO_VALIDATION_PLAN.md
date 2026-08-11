# NM/WA Smoke/Demo Validation Plan (Sprints 1–10)

Offline synthetic only. No live ingest, scraping, source activation, or external URLs.

## Objective

Prove an operator can inspect NM/WA classify+match outputs and review/report
surfaces end-to-end via a smoke/demo path that yields a real `run_id` with
per-surface PASS/FAIL/NOT_RUN (or honest NOT_RUN with blocker reason).

## Contract

- Service: `nm_wa_smoke_validation_contract_service`
- Statuses: PASS | FAIL | NOT_RUN only
- Run id: `nf_os_smoke_YYYYMMDDTHHMMSSZ_<8 hex>`
- No fabricated PASS or run_id

## Expected surfaces

See `EXPECTED_SURFACES` in the contract service / smoke manifest.

## Hard stops

Missing NM/WA/combined surfaces; hidden missing-data; missing human-review or
next-check; final eligibility without evidence; network/live activation.

## Out of scope

Scoring math, classify/match logic changes, auth, migrations, production mutation.
