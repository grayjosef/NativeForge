# NM/WA Playwright E2E Enablement Plan (Sprints 1–10)

## Discovery (confirmed)

- Frontend: Vite + React + Vitest (`frontend/`)
- Playwright: **absent** (no deps, no config, no e2e/)
- Demo route already present: `/?view=nm_wa_operator_demo` (static JSON bridge)
- Prior demo-runtime smoke PASS: `nf_os_browser_20260811T094927Z_920a291f`
- `uv.lock` must remain untouched; Playwright is an npm frontend tooling change only

## Contract

- Statuses: PASS | FAIL | NOT_RUN only
- Run id: `nf_os_playwright_YYYYMMDDTHHMMSSZ_<8 hex>`
- Route: `/?view=nm_wa_operator_demo`
- Artifacts: `artifacts/nm_wa_playwright_smoke/`
- Distinguish from demo-runtime/static smoke

## Next

Install minimal Playwright locally, add E2E smoke for 14 screens, runner, execute, closeout.
