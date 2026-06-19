# NativeForge Handoff — Block NF-5: Operator Workbench UX v1 (Sprints 227–241)

**Date:** 2026-05-19  
**Branch:** `main` (ahead of `origin/main`)  
**Push:** Not performed (per governance)  
**Stash:** Preserved — `stash@{0}: wip-sprint8-ui-redesign-do-not-commit`

## Run summary

Completed the approved 15-sprint Stage 11 operator workbench block with green baseline first (`5032` passed). Presentational + wiring only: Vite/React workbench screens consume read-only FastAPI advisory bundles and existing discovery/local-DB endpoints. No scoring, relevance, matching logic, hard invariants, or human gates were changed.

| Sprint | Commit | Summary |
|--------|--------|---------|
| 227 | `4be8e16` | `nf_workbench` feature flag (`?nf_workbench=1` / localStorage) |
| 228 | `b95a7f4` | Operator workbench advisory service (synthetic fixture corpus) |
| 229 | `c551403` | Advisory routes + `main.py` router wiring (`nf_workbench` query required) |
| 230 | `c8f125e` | `workbenchApiClient` HTTP client |
| 231 | `67101b6` | `WorkbenchStateBadges` + Stage 11 tab types |
| 232 | `09fe91f` | Source review queue screen (local DB review items) |
| 233 | `81040b6` | Discovery / intake review screen (Stage 5 advisory preview) |
| 234 | `45ed602` | Native relevance review screen (8 labels + confidence + evidence) |
| 235 | `b792a76` | Org / applicant profile screen (UNKNOWN surfaced) |
| 236 | `0335fd6` | Matching + readiness screen (fit dimensions, blockers, next-action) |
| 237 | `7e59898` | Operator ledger + decision pack screen |
| 238 | `7c7599a` | `WorkbenchStage11` tabbed shell |
| 239 | `7bf055d` | `WorkbenchPage` wiring (flag on → Stage 11; off → legacy grid) |
| 240 | `fac3ce8` | Stage 11 CSS (tabs, badges, preview cards) |
| 241 | `a8a14f5` | Frontend smoke tests + Stage 11 closeout packet |

**Iterations used:** 15 product sprints (within leash)

## Build / test state

- **Baseline at block start:** `5032 passed`, `11 skipped`, `0 failed`
- **Full pytest (final):** `5041 passed`, `11 skipped`, `0 failed` (+9 tests)
- **Ruff:** Green on new backend files
- **Frontend:** `npm run typecheck`, `npm test` (23 passed), `npm run build` — all green
- **Alembic head:** `0019` (no new migrations)
- **Stash:** Untouched
- **uv.lock:** Not staged or committed

## Stage 11 smoke verification (Sprint 241)

**run_id:** `smoke-1781879593654` (vitest `workbenchStage11Smoke.test.tsx`)

| Screen | Result |
|--------|--------|
| source-review-queue | PASS |
| discovery-intake-review | PASS |
| native-relevance-review | PASS |
| org-applicant-profile | PASS |
| matching-readiness | PASS |
| workbench-stage11-shell | PASS |

Closeout packet: `build_operator_workbench_stage11_closeout_packet` reports `smoke_verification_passed: true` when all six canonical screens pass.

## Architecture

### Feature flag

- **Frontend:** `readWorkbenchFlag()` — `?nf_workbench=1` or `localStorage` key `nf-workbench-enabled`
- **API:** `nf_workbench=true` query param required on `/discovery/operator-workbench-advisory/*` (403 without flag)

### Advisory layers wired (read-only)

| Screen | Data source |
|--------|-------------|
| Source review queue | Local DB via existing discovery review-items API |
| Discovery / intake | `funding_opportunity_intake_*` synthetic previews |
| Native relevance | `native_relevance_classification_*` previews |
| Org / applicant profile | `org_applicant_profile_*` previews |
| Matching + readiness | `matching_readiness_*` (canonical fit via `eligibility_fit_assessment_*`) |
| Ledger / decisions | Existing `operator-decision-pack`, ledger summary, open actions |

### Hard invariants preserved (UI surfaces honestly)

- `needs_operator_review`, `UNKNOWN`, `overclaim_blocked` badges visible
- No path to verified/approved without explicit operator action
- `synthetic_fixtures_only` / `preview_only` / `no_live_ingestion` on advisory payloads

## Key decisions

1. **Green baseline first** before any feature commit.
2. **Behind `nf_workbench`** — legacy workbench grid unchanged when flag off.
3. **Advisory service composes existing Stage 5–10 services** — no duplicate evaluators.
4. **Local dev only** — no live ingestion, scraping, LLM runtime, source activation, or new migrations.
5. **NativeForge language only** — no ContractForge/Spark branding in Stage 11 UX.

## Risks / needs human

- **Not pushed** — review required before `git push`.
- **Operator ledger screen** reuses existing `PriorityActionsCard` / `OperatorLedgerCard` — full ledger tab UX may need polish in a follow-on sprint.
- **Production wiring** out of scope until separate human authorization.

## Proposed next safe action

1. Push and review the 15 commits (+ handoff) on `main`.
2. Manual QA: start API + frontend with `?nf_workbench=1` against local demo org.
3. Consolidate operator guidance overlap (`eligibility_fit_assessment_*` vs `matching_readiness_*`) before enabling flag by default.

## Verification commands

```bash
cd /home/josefgray/projects/nativeforge
source .venv/bin/activate
pytest -q
cd frontend && npm run typecheck && npm test && npm run build
git log --oneline -16
git stash list
pytest tests/test_sprint241_operator_workbench_stage11_closeout_packet.py -q
```
