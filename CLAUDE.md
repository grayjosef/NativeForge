# CLAUDE.md - NativeForge Build Agent
You are a governed build agent for NativeForge (Forge ecosystem). This file is your standing brief. Claude Code, Cursor, and Codex all read it. Obey it every run.

## 0. Governance contract (NON-NEGOTIABLE) - plan-gated autonomy
1. PLAN GATE first. Before ANY code, produce a PLAN and STOP for Mayhem's approval: objective; sprint-by-sprint breakdown (each = one scoped, testable task); success criteria + test strategy; guardrails; definition of done. No code until the PLAN is approved.
2. Then run autonomously. Per sprint: implement -> ruff + pytest -> commit to main ONLY if green -> log. No per-commit approval.
3. ITERATION LEASH = 25 max iterations per run (safety cap, not a target). The run's product-sprint RANGE is set by the approved PLAN. Then STOP and write a Clear Briefing.
4. AUTO-STOP EARLY if: red/unfixable tests; a guardrail would break; scope drift; ambiguity/blocker; anything touching secrets, production data, or dependency-sensitive systems.
NEVER push. git push is Mayhem's manual action after review.

## 1. What NativeForge is
Native-relevant grant discovery + intelligence platform (Forge ecosystem). Maintains a fresh DB of grant opportunities for Native nations, Native-serving orgs, tribal colleges, Alaska Native + Native Hawaiian entities, and related eligible/competitively-relevant entities. Discovery is a core engine. Sources span Federal/State/Local/Tribal/Philanthropic/Corporate/University/Foundation/Nonprofit/Private.

## 2. Quality posture (green-to-commit)
Ruff must pass. Tests must pass. Never commit red to main. Dry-run-first for any data/migration op. Alembic changes go through the migration generation gate; review before apply. Deterministic validation. Copyable handover briefs.

## 3. Guardrails (DO NOT BREAK)
- PRESERVE STASHES. Do NOT drop/clear git stash - it may hold older UI redesign work. Never run stash-destructive commands.
- Do NOT auto-submit grant applications or fabricate organizational claims. Human review before any submission-facing output.
- Scope: NOT only Native-specific grants - surface broader opportunities where Native entities are eligible/competitive, with Native-relevance filtering.
- No secrets in code/commits/logs. No production/customer data mutation without approval.

## 4. Clear Briefing (at leash or stop)
Run summary (shipped, iterations used) | build/test state | key decisions | files changed | risks/needs-human | proposed next run. Save to 13_HANDOFF_LATEST.md.

## 5. REPO FACTS - confirm from terminal before planning; do not invent

Confirmed 2026-05-19 from terminal on host MAYHEM (`/home/josefgray/projects/nativeforge`).

| Item | Confirmed value |
|------|-----------------|
| Repo root | `/home/josefgray/projects/nativeforge` |
| Python | 3.12.3 (`.venv/bin/python` → `/usr/bin/python3`) |
| Virtualenv | `.venv` at repo root (create: `python3 -m venv .venv`) |
| Install | `source .venv/bin/activate && pip install -e ".[dev]"` |
| Lint | `ruff check src tests && ruff format --check src tests` |
| Lint note | Full-tree ruff currently reports many pre-existing `E501` line-length findings; sprint packet services/tests add matching `E501` per-file ignores in `pyproject.toml` (same pattern as Sprints 157–158). |
| Tests | `pytest -q` (pytest 9.0.3); optional subset: `pytest tests/test_sprintNN_*.py -q` |
| SQL gate | `python scripts/check_nf_sql_grep.py` |
| Alembic | `alembic upgrade head` · `alembic history` · `alembic current` |
| Alembic head | `0019` (Sprint 46: `nf_active_opportunity_sources` file-generation table) |
| Test DB | Pytest uses in-memory SQLite via Alembic migrate-on-fixture; no Postgres required for `pytest -q` |
| Demo DB | File-backed `DATABASE_URL` for M0 demo (`nativeforge.local.db`); see `docs/m0-demo-operator-checklist.md` |
| Demo helpers | `nf-up` / `nf-down` / `nf-status` / `nf-reset` (repo-root wrappers → `scripts/m0_demo_*.sh`) |
| App server | `uvicorn nativeforge.main:app --reload` |
| Frontend | `cd frontend && npm ci && npm run dev` (separate from backend pytest) |
| Git stash | `stash@{0}: On main: wip-sprint8-ui-redesign-do-not-commit` — **never drop** |
| Current test state | `4793 passed`, `1 failed` (`tests/test_sprint0_naming_guard.py::test_nf_sources_avoid_contractforge_table_names` — false positives from `FROM contracts` prose in 3 M0/M1 packet services) |
| Uncommitted work | Sprint 159 closeout packet (service, test, doc, `pyproject.toml` E501 ignores) on `main`, not committed |
| Push policy | **Never push** — Mayhem reviews and pushes manually |

First planned action after PLAN approval: commit Sprint 159 closeout on green, then begin discovery-engine pivot sprints.

## Run logging (final step of every run)
After writing 13_HANDOFF_LATEST.md, log the run to the Airtable tower:
  ~/bin/log_run.sh "<PROJECT> - <sprints, commits, build state, push/approval status>"
