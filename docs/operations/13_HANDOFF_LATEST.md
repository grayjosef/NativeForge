# NativeForge Handoff — Block NF-9: Real-Resolver Validation + First Tier-1 Activation (Sprints 287–301)

**Date:** 2026-05-19  
**Branch:** `main` (ahead of `origin/main`)  
**Push:** Not performed (per governance)  
**Stash:** Preserved — `stash@{0}: wip-sprint8-ui-redesign-do-not-commit`

## Run summary

Completed the approved 15-sprint block with green baseline first (`5103` passed). Swapped the synthetic URL resolver for a rate-limited real HEAD/GET resolver with posture detection, ran real seed-preview reporting with baseline comparison, activated exactly **one** source (`nf-seed-2026-fed-001`) through the human gate, and verified real tier-1 fetch with canonical-id idempotent upsert. **Stopped after fed-001** — no other sources activated.

| Sprint | Commit | Summary |
|--------|--------|---------|
| 287 | `465f108` | Real URL resolver (HEAD/GET, rate-limited, posture detection) |
| 288 | `a8fd137` | Real URL quality verification with detected posture |
| 289 | `1525f0b` | Synthetic vs real baseline comparison (156/18/3 baseline) |
| 290 | `f559f4e` | Real-resolver seed preview report (177 candidates) |
| 291 | `07901be` | Human-gated activation for `nf-seed-2026-fed-001` only |
| 292 | `d6d175e` | Real tier-1 live fetch + idempotent upsert |
| 293 | `a94d3fe` | Real-resolver validation plan gate |
| 294 | `6cb7919` | Full validation orchestrator (preview → activate → fetch) |
| 295 | `a84bf2f` | Gate verification service |
| 296 | `36b463d` | Closeout packet |
| 297 | `f900fe8` | Plan-gated API routes |
| 298–301 | *(handoff)* | Block closeout |

## Plan gate (quadruple gate)

| Gate | Value |
|------|-------|
| `NF_APP_ENV` | `staging` |
| Env | `NF_LIVE_SOURCE_INGESTION_PLAN_APPROVED=true` |
| Env | `NF_REAL_RESOLVER_VALIDATION_PLAN_APPROVED=true` |
| Query | `nf_live_source_ingestion=true` |
| Query | `nf_real_resolver_validation=true` |

## Synthetic baseline (NF-8 hint-based)

| Posture | Count |
|---------|-------|
| public | 156 |
| login | 18 |
| members | 3 |
| dead | 0 |

Real-resolver run produces `baseline_comparison` with `real_counts`, `deltas`, and corrected `posture_counts` per candidate. CI uses injectable mock fetcher; staging deployment uses live HTTP.

## fed-001 activation (human gate)

- **Authorized seed:** `nf-seed-2026-fed-001` only
- **Path:** `activate_single_seed_source_human_gate()` with operator confirmation payload
- **Result:** exactly one registry row with `is_active=True`; all others remain inactive
- **Confirmation keys required:** `operator_handle`, `human_activation_acknowledged`, `public_only_acknowledged`, `single_source_only_acknowledged`

## Tier-1 live fetch (fed-001)

- Rate-limited (1 req/s default)
- Max 3 opportunities per run (no bulk crawl)
- Canonical opportunity id upsert: second run inserts 0
- Public only — HTTP 4xx blocks fetch; no CAPTCHA/login bypass; no credentials

## API endpoints

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/v1/nf/{demo\|real}/orgs/{org_id}/discovery/source-ingestion/real-resolver-seed-preview` | Real-resolver 177-candidate report + baseline comparison |
| POST | `/v1/nf/{demo\|real}/orgs/{org_id}/discovery/source-ingestion/real-resolver-validation` | Full block: preview + fed-001 activation + tier-1 fetch |

POST body = operator confirmation dict (see above).

## Build / test state

- **Baseline at block start:** `5103 passed`, `11 skipped`, `0 failed`
- **Full pytest (final):** `5116 passed`, `11 skipped`, `0 failed` (+13 tests)
- **Ruff:** Green on all NF-9 files
- **Frontend:** No changes
- **Alembic head:** `0019` (no new migrations)
- **Stash:** Untouched

## Hard invariants preserved

- Staging only; production fail-closed
- Exactly one source activated (`nf-seed-2026-fed-001`)
- members/login → BLOCKED; never bypassed
- No credentials; no CAPTCHA/login bypass
- Rate-limited resolver and tier-1 fetch
- Idempotent upsert on canonical opportunity id
- CI uses mock HTTP — no live network in test suite

## Proposed next safe action

1. Deploy to staging with all plan-gate env vars set.
2. POST `real-resolver-validation` with operator confirmation; review corrected posture table vs baseline.
3. Monitor fed-001 as the sole active source; do not activate additional sources without separate authorization.

## Verification commands

```bash
cd /home/josefgray/projects/nativeforge
source .venv/bin/activate
pytest -q
pytest tests/test_sprint28*_real*.py tests/test_sprint29*_*.py -q
git log --oneline 0a8b48c..HEAD
git stash list
```
