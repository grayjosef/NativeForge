# NativeForge Handoff — Block NF-8: Staging Activation Dry-Run (Sprints 272–286)

**Date:** 2026-05-19  
**Branch:** `main` (ahead of `origin/main`)  
**Push:** Not performed (per governance)  
**Stash:** Preserved — `stash@{0}: wip-sprint8-ui-redesign-do-not-commit`

## Run summary

Completed the approved 15-sprint staging activation dry-run block with green baseline first (`5086` passed). Added staging-only guards, triple plan gate, full 177-candidate seed preview report, single tier-1 dry fetch with idempotent upsert verification, activation-ready recommendations, and plan-gated API routes. **Stopped before any source activation** — no `is_active=True` anywhere.

| Sprint | Commit | Summary |
|--------|--------|---------|
| 272 | `1262f5f` | Staging environment guard (`NF_APP_ENV=staging`; production fail-closed) |
| 273 | `a1e972e` | Staging activation dry-run plan gate (staging + live ingestion flags) |
| 274 | `480d1c3` | Full seed preview report with URL quality + posture per candidate |
| 275 | `b28cbf7` | Seed preview report tests |
| 276 | `f5a2d23` | Tier-1 single-source rate-limited dry fetch service |
| 277 | `f987281` | Tier-1 idempotent upsert path tests (second run = 0 new) |
| 278 | `c82586d` | Activation-ready report (green vs BLOCKED; no activation) |
| 279 | `4781012` | Staging activation dry-run orchestrator |
| 280 | `5f41d1b` | Plan-gated API routes + production block tests |
| 281 | `8992c32` | Gate verification service |
| 282 | `0087610` | Closeout packet |
| 283–285 | *(folded into 280/273 hardening)* | Production env 403 on routes; non-staging gate rejection |
| 286 | *(this handoff)* | Block closeout |

**Iterations used:** 11 product commits + hardening + handoff (within leash)

## Staging plan gate (triple gate)

All dry-run paths require **all** of:

| Gate | Value |
|------|-------|
| `NF_APP_ENV` | `staging` (production/local fail-closed) |
| Env | `NF_LIVE_SOURCE_INGESTION_PLAN_APPROVED=true` |
| Query | `nf_live_source_ingestion=true` |
| Query | `nf_staging_activation_dry_run=true` |

## Seed preview report (177 candidates)

Deterministic dry-run against seed CSV (synthetic URL resolver in CI):

| Metric | Count |
|--------|-------|
| Total candidates | 177 |
| URL resolved | 177 |
| Dead URLs | 0 |
| Public posture | 156 |
| Login posture | 18 |
| Members posture | 3 |
| BLOCKED/referral (members + login) | 21 |

Each candidate row includes: `url_status` (`resolved`/`dead`), `access_posture`, `access_posture_blocked`, `referral_required`, `is_active: false`.

## Tier-1 dry fetch (single source)

- **Source:** first tier-1 federal adapter candidate (`nf-seed-2026-fed-001`)
- **Rate limit:** 1 request / second minimum interval
- **Upsert path:** first run inserts 1 canonical opp id; second run inserts 0 (idempotent verified)
- **No bulk crawl**

## Activation-ready report (STOP — no activation)

| Tier-1 status | Count |
|---------------|-------|
| GREEN (public + resolved) | 61 |
| BLOCKED (members/login) | 0 |
| NOT_READY (dead URL) | 0 |

**Recommended first human activation candidate:** `nf-seed-2026-fed-001`  
**Blocked tier-3 examples:** Native Ways Federation Members, NIHB, NCAI (members posture)

No source was activated. All candidates remain `is_active=False`.

## API endpoints (staging dry-run)

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/v1/nf/{demo\|real}/orgs/{org_id}/discovery/source-ingestion/staging-seed-preview-report` | 177-candidate quality report |
| GET | `/v1/nf/{demo\|real}/orgs/{org_id}/discovery/source-ingestion/staging-activation-dry-run` | Full dry-run (preview + tier-1 + activation-ready) |

## Build / test state

- **Baseline at block start:** `5086 passed`, `11 skipped`, `0 failed`
- **Full pytest (final):** `5103 passed`, `11 skipped`, `0 failed` (+17 tests)
- **Ruff:** Green on all NF-8 staging files
- **Frontend:** No changes
- **Alembic head:** `0019` (no new migrations)
- **Stash:** Untouched
- **uv.lock:** Not staged or committed

## Hard invariants preserved

- Staging only — production environment returns 403 on dry-run routes
- Human activation gate untouched — dry-run stops before activation
- No `is_active=True` set anywhere
- members/login → BLOCKED/referral; never bypassed
- No credentials; rate-limited tier-1 fetch; idempotent upsert
- Synthetic resolver in CI — no live HTTP in test suite
- NativeForge language only

## Key decisions

1. **Triple gate** — staging env + NF-7 plan gate + dry-run query flag.
2. **Route-level staging check** — `is_staging_activation_dry_run_approved()` requires `NF_APP_ENV=staging`.
3. **Activation-ready report is advisory only** — lists top-10 GREEN tier-1 candidates; operator must activate manually.
4. **Tier-1 dry fetch uses synthetic payload in CI** — production staging can inject live fetcher when authorized.

## Risks / needs human

- **Not pushed** — review required before `git push`.
- **Staging deployment** must set `NF_APP_ENV=staging` and plan gate env vars before calling dry-run endpoints.
- **Live URL resolver** on staging still requires separate authorization (CI uses synthetic resolver).
- **Activation is the next human gate** — dry-run explicitly does not activate sources.

## Proposed next safe action

1. Deploy to staging with `NF_APP_ENV=staging` + `NF_LIVE_SOURCE_INGESTION_PLAN_APPROVED=true`.
2. Call `staging-activation-dry-run` for one org; review activation-ready report.
3. Human operator activates **one** tier-1 GREEN source when authorized — never bulk activate.

## Verification commands

```bash
cd /home/josefgray/projects/nativeforge
source .venv/bin/activate
pytest -q
ruff check src/nativeforge/services/staging*.py src/nativeforge/api/source_ingestion_routes.py
pytest tests/test_sprint27*_staging*.py tests/test_sprint28*_staging*.py -q
NF_APP_ENV=staging NF_LIVE_SOURCE_INGESTION_PLAN_APPROVED=true \
  python -c "from nativeforge.services.staging_activation_dry_run_orchestrator_service import run_staging_activation_dry_run; print(run_staging_activation_dry_run()['activation_ready_report']['green_count'])"
git log --oneline db7d9a1..HEAD
git stash list
```
