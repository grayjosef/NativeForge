# NativeForge Handoff — Block NF-7: Live Source Ingestion (real seed) (Sprints 257–271)

**Date:** 2026-05-19  
**Branch:** `main` (ahead of `origin/main`)  
**Push:** Not performed (per governance)  
**Stash:** Preserved — `stash@{0}: wip-sprint8-ui-redesign-do-not-commit`

## Run summary

Completed the approved 15-sprint live source ingestion block with green baseline first (`5065` passed). Ingested the real 177-row seed CSV into discovery as inactive candidates, added URL quality + access posture verification, tier-1/2/3 adapter scaffolding, plan-gated API routes, gate verification, and closeout packet. Hard gates preserved: human activation before scrape, public-only automation, members/login blocked, no credentials, rate-limited, idempotent upserts. Synthetic fixtures only in tests — no live HTTP in the test suite.

| Sprint | Commit | Summary |
|--------|--------|---------|
| 257 | `3bcd0d3` | `NF_SOURCE_SEED_2026.csv` (177 rows) + seed schema contract + generator |
| 258 | `4f838c4` | Seed CSV loader → discovery candidates (`is_active=False`) |
| 259 | `4f47a06` | URL resolve + access posture (`public` / `members` / `login`) |
| 260 | `d15c08e` | Plan gate (`NF_LIVE_SOURCE_INGESTION_PLAN_APPROVED`) |
| 261 | `b318c71` | Tier-1 federal adapter (Grants.gov / Simpler / GrantSolutions) |
| 262 | `78161cb` | Tier-1 idempotent upsert on canonical opportunity id (tests) |
| 263 | — | *(covered by sprint 262 commit — tier-1 test file)* |
| 264 | `5ef33c6` | Tier-2 state portal adapter registry + tests |
| 265 | — | *(covered by sprint 264 commit — tier-2 tests bundled)* |
| 266 | `91ccd00` | Tier-3 foundation/directory discovery + dedupe + freshness refresh |
| 267 | — | *(covered by sprint 266 commit — tier-3 tests bundled)* |
| 268 | `9fd4d95` | Orchestrator: seed → quality → tier routing preview + registry persist |
| 269 | `0453b8e` | Plan-gated API routes (`nf_live_source_ingestion=true`) + main wiring |
| 270 | `1304bb3` | Gate verification service |
| 271 | `05f52e8` | Closeout packet |

**Iterations used:** 12 product commits covering 15 sprints (within leash; 263/265/267 folded into adjacent commits)

## Seed dataset (`NF_SOURCE_SEED_2026.csv`)

| Metric | Count |
|--------|-------|
| Total sources | 177 |
| Tier 1 (federal) | 61 |
| Tier 2 (state portals) | 52 |
| Tier 3 (foundation/org) | 64 |
| Access posture: public | 156 |
| Access posture: login | 18 |
| Access posture: members | 3 |

**Path:** `fixtures/source_ingestion/NF_SOURCE_SEED_2026.csv`  
**Generator:** `scripts/generate_nf_source_seed_2026.py`

## Architecture (services)

| Service | Role |
|---------|------|
| `source_ingestion_seed_schema_service` | CSV column contract + row count guard |
| `source_ingestion_seed_loader_service` | Parse CSV → inactive discovery candidates |
| `source_ingestion_url_quality_service` | URL resolve + posture; members/login → `access_posture_blocked` |
| `source_ingestion_plan_gate_service` | Env + query flag double gate |
| `source_ingestion_tier1_federal_adapter_service` | Federal parser; canonical opp id; idempotent upsert |
| `source_ingestion_tier2_state_adapter_service` | State portal registry; public listings only |
| `source_ingestion_tier3_foundation_adapter_service` | Directory self-extension (NAP, AIHEC, Native Ways); dedupe + freshness |
| `source_ingestion_orchestrator_service` | End-to-end preview; `persist_seed_candidates_to_registry()` |
| `source_ingestion_gate_verification_service` | Block gate checks |
| `source_ingestion_closeout_packet_service` | Deterministic closeout artifact |

## API (plan-gated)

Requires **both**:
- Query: `nf_live_source_ingestion=true`
- Env: `NF_LIVE_SOURCE_INGESTION_PLAN_APPROVED=true`

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/api/v1/orgs/{org_id}/discovery/source-ingestion/seed-preview` | Preview seed → quality → tier routing |
| POST | `/api/v1/orgs/{org_id}/discovery/source-ingestion/load-seed-candidates` | Persist inactive candidates to registry |

## Build / test state

- **Baseline at block start:** `5065 passed`, `11 skipped`, `0 failed`
- **Full pytest (final):** `5086 passed`, `11 skipped`, `0 failed` (+21 tests)
- **Ruff:** Green on all NF-7 source ingestion files + seed generator
- **Frontend:** No changes in this block
- **Alembic head:** `0019` (no new migrations)
- **Stash:** Untouched
- **uv.lock:** Not staged or committed

## Hard invariants preserved

- Candidates load with `is_active=False`, `verification_status=unverified`, `human_activation_required=True`
- No opportunity scrape without explicit human activation per source
- `members` / `login` postures → `access_posture_blocked=True`; referral only, never bypassed
- No credentials stored or used
- Rate-limited adapter design; idempotent upsert on canonical opportunity id
- Tests use synthetic URL resolver — no live network in CI
- NativeForge language only — no ContractForge/Spark branding

## Gate verification (sprint 270)

`verify_source_ingestion_gates()` checks:

- Seed row count = 177
- All candidates inactive; human activation required
- No scrape without activation
- Quality batch covers all rows; blocked postures present
- Tier-1 idempotent upsert

Closeout packet reports `gate_verification_passed: true` when all checks pass.

## Key decisions

1. **Real seed CSV** generated in-repo (177 rows) because upstream file was absent.
2. **Double plan gate** (env + query flag) for any live-ingestion API surface.
3. **Tier adapters are scaffolding** — synthetic fixtures in tests; production crawl requires per-source human activation.
4. **Tier-3 directory discovery** self-extends from NAP/AIHEC/Native Ways member lists with canonical-id dedupe.
5. **Sprint numbering gaps** (263, 265, 267) — work landed in adjacent commits to avoid empty commits.

## Risks / needs human

- **Not pushed** — review required before `git push`.
- **Live URL verification** not exercised in CI; operator should run seed-preview against staging with real resolver when authorized.
- **Tier-2/3 scrapers** are light per-portal stubs — production hardening is follow-on work per portal.
- **21 login/members sources** will remain blocked until manual referral workflow is defined.

## Proposed next safe action

1. Review the 12 NF-7 commits (+ handoff) on `main`.
2. Set `NF_LIVE_SOURCE_INGESTION_PLAN_APPROVED=true` in staging; call seed-preview for one org.
3. Operator review: load seed candidates, inspect URL quality report, activate sources one-by-one before enabling tier adapters.

## Verification commands

```bash
cd /home/josefgray/projects/nativeforge
source .venv/bin/activate
pytest -q
ruff check src/nativeforge/services/source_ingestion*.py \
  src/nativeforge/api/source_ingestion_routes.py \
  scripts/generate_nf_source_seed_2026.py
pytest tests/test_sprint25*_source_ingestion*.py \
  tests/test_sprint26*_source_ingestion*.py \
  tests/test_sprint27*_source_ingestion*.py -q
git log --oneline f4cfd41..HEAD
git stash list
```
