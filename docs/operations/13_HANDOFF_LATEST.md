# NativeForge Handoff — Block NF-6: Future-state Demo Path + Beta Hardening (Sprints 242–256)

**Date:** 2026-05-19  
**Branch:** `main` (ahead of `origin/main`)  
**Push:** Not performed (per governance)  
**Stash:** Preserved — `stash@{0}: wip-sprint8-ui-redesign-do-not-commit`

## Run summary

Completed the approved 15-sprint Stage 12 block with green baseline first (`5041` passed). Reconciled NF-4 cleanup candidates first, then built an isolated fictional demo dataset (`nf_stage12` namespace) and a guided first-use flow through the operator workbench. Presentational + wiring only; all hard invariants and human gates preserved.

| Sprint | Commit | Summary |
|--------|--------|---------|
| 242 | `d491714` | Reconcile `operator_next_check` → canonical `next_actions` |
| 243 | `e471069` | Canonicalize `application_readiness` on `readiness_label` |
| 244 | `247ab13` | Isolated Stage 12 demo fixtures (sources, 4 opps, profile) |
| 245 | `309ccad` | Demo dataset loader + namespace isolation guards |
| 246 | `39bdde9` | Safe demo reset descriptor (no DB writes) |
| 247 | `9193c8b` | Guided flow step vocabulary (8 steps) |
| 248 | `e7b850f` | Guided demo path advisory service |
| 249 | `2a34cfd` | Stage 12 API routes (`nf_stage12_demo` flag required) |
| 250 | `ff3c255` | Frontend feature flag + API client |
| 251 | `d457372` | Guided flow types + stepper |
| 252 | `f9f64a7` | Review screens (discovery, quality, intake, relevance, match) |
| 253 | `6db16ba` | Activation readiness preview step (no execution) |
| 254 | `479f377` | Operator decision + evidence steps; WorkbenchPage wiring |
| 255 | `de88717` | Beta hardening gate verification + CSS |
| 256 | `f3a5e57` | Full-flow smoke tests + closeout packet |

**Iterations used:** 15 product sprints (within leash)

## NF-4 reconciliation (completed first)

| Cleanup candidate | Resolution |
|-------------------|------------|
| `operator_next_check` overlap | `canonical_operator_guidance_reconciliation_service` maps fit topics → `matching_readiness` `next_actions`; exposed as `canonical_next_actions` on fit records |
| `application_readiness` vs `readiness_label` | `readiness_terminology_reconciliation_service` canonicalizes on `readiness_label`; org profile records include both legacy + canonical fields |

Gate verification (`matching_readiness_stages8_10_gate_verification`) updated: `reconciliation_cleanup_candidates` now empty.

## Build / test state

- **Baseline at block start:** `5041 passed`, `11 skipped`, `0 failed`
- **Full pytest (final):** `5065 passed`, `11 skipped`, `0 failed` (+24 tests)
- **Ruff:** Green on new backend files
- **Frontend:** `npm run typecheck`, `npm test` (33 passed), `npm run build` — all green
- **Alembic head:** `0019` (no new migrations)
- **Stash:** Untouched
- **uv.lock:** Not staged or committed

## Isolated demo dataset (`nf_stage12`)

| Asset | Count | Notes |
|-------|-------|-------|
| Sources | 2 | Fictional namespaced (`nf_stage12_src_*`) |
| Opportunities | 4 | native_specific, broadly_eligible, weak/uncertain, stale/expired |
| Profile | 1 | Red Cedar Nation (fictional tribal government demo) |

All fixtures under `fixtures/stage12_demo_path/` with `demo_namespace: nf_stage12`, `fictional_only: true`. Loader enforces namespace + explicit demo context.

## Guided flow (8 steps)

1. Source discovery  
2. Source quality review  
3. Activation readiness (**preview only**, `may_activate_now: false`)  
4. Opportunity intake (stale shown honestly)  
5. Native relevance review (evidence + broad-vs-specific labels)  
6. Profile match + readiness (`needs_operator_review`, no final eligibility)  
7. Operator decision (no verified/approved without operator action)  
8. Evidence / audit trail (synthetic audit preview)

**Flags:** `?nf_workbench=1&nf_stage12_demo=1` on frontend; API requires `nf_stage12_demo=true`.

## Sprint 256 smoke verification (real vitest run)

**run_id:** `stage12-smoke-1781882733211`

| Step | Result |
|------|--------|
| source-discovery | PASS |
| source-quality-review | PASS |
| activation-readiness-preview | PASS |
| opportunity-intake | PASS |
| native-relevance-review | PASS |
| profile-match-readiness | PASS |
| operator-decision | PASS |
| evidence-audit-trail | PASS |
| guided-demo-shell | PASS |

Closeout packet: `build_stage12_guided_demo_closeout_packet` reports `smoke_verification_passed: true` when all eight canonical steps pass.

## Hard invariants preserved

- No source activation execution
- No live ingestion, scraping, LLM runtime, or new migrations
- `needs_operator_review`, `UNKNOWN`, `overclaim_blocked`, stale/expired surfaced honestly
- Nothing reaches verified/approved/active without explicit operator action
- Demo data fully isolated from production/other namespaces

## Key decisions

1. **Reconcile NF-4 terminology first** before demo wiring.
2. **`nf_stage12` namespace** on all fictional fixtures — contamination guard in loader.
3. **Stage 12 overlays Stage 11** when both `nf_workbench` and `nf_stage12_demo` flags on.
4. **Demo reset** is descriptor-only (clears guided-flow localStorage keys; no DB writes).
5. **NativeForge language only** — no ContractForge/Spark branding.

## Risks / needs human

- **Not pushed** — review required before `git push`.
- **Manual QA** recommended: `?view=workbench&nf_workbench=1&nf_stage12_demo=1` against local API.
- **Production demo path** out of scope until separate human authorization.

## Proposed next safe action

1. Push and review the 16 commits (+ handoff) on `main`.
2. Manual walkthrough of full guided path with local demo org.
3. Consider persisting guided-step progress in localStorage (currently stepper state is session-only).

## Verification commands

```bash
cd /home/josefgray/projects/nativeforge
source .venv/bin/activate
pytest -q
cd frontend && npm run typecheck && npm test && npm run build
git log --oneline -17
git stash list
pytest tests/test_sprint256_stage12_closeout_packet.py -q
pytest tests/test_sprint255_stage12_beta_hardening_gate.py -q
```
