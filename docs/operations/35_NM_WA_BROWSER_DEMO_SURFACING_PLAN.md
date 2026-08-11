# NM/WA Browser/UI Demo Surfacing Plan (Sprints 1–10)

## Safe path (discovered)

- Frontend: Vite + React + Vitest (`frontend/`), surfaces via `?view=`
- Playwright/e2e: **not installed** — true Playwright browser smoke is NOT_RUN
- Supported unattended mode: **demo-runtime static/Vitest** over offline fixtures
- Prefer read-only `?view=nm_wa_operator_demo` page + static JSON bridge
- Do not require live API, org headers, or auth changes

## Contract

- Statuses: PASS | FAIL | NOT_RUN only
- Run id: `nf_os_browser_YYYYMMDDTHHMMSSZ_<8 hex>`
- Prior offline smoke run_id retained for lineage

## Out of scope

Scoring/match/auth/migration/source-activation changes; new state pilots; ContractForge language.
