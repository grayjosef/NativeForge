# NativeForge Handoff — Block NF-1: Funding Opportunity Intake Hardening (Sprints 167–181)

**Date:** 2026-05-19  
**Branch:** `main` (ahead of `origin/main` by 15 commits)  
**Push:** Not performed (per governance)  
**Stash:** Preserved — `stash@{0}: wip-sprint8-ui-redesign-do-not-commit`

## Run summary

Completed the approved 15-sprint Stage 5 funding opportunity intake hardening block with green baseline first. All work is preview-only, synthetic fixtures, fail-closed advisory — no live ingestion, scraping, external URLs, LLM runtime, or source activation.

| Sprint | Commit | Summary |
|--------|--------|---------|
| 167 | `63bfdb9` | Per-field confidence vocabulary (`confirmed` / `high` / `medium` / `low` / `unknown` / `conflicting`) |
| 168 | `03d7dba` | Field-level provenance contract |
| 169 | `646c700` | Provenance-first opportunity record builder |
| 170 | `fa34abb` | Missing-data flags contract |
| 171 | `d681950` | Intake status model |
| 172 | `c7f8948` | Fail-closed gate evaluator (deadline, source, provenance, stale, duplicate) |
| 173 | `d18cf39` | Operator-approved duplicate detection |
| 174 | `86a5818` | Synthetic demo fixture corpus (`fixtures/funding_opportunity_intake/demo_records.json`) |
| 175 | `6c93490` | Hardened opportunity record assembly |
| 176 | `0d6cced` | Discovery intake bridge — hardened preview on intake run summaries |
| 177 | `780e7ba` | Per-field confidence rollup |
| 178 | `4c840f0` | Operator review queue metadata |
| 179 | `4890288` | Stage 5 gate verification on demo corpus |
| 180 | `54c48ce` | Stage 5 verification rollup |
| 181 | `cdd4405` | Stage 5 funding opportunity intake closeout packet |

**Iterations used:** 15 product sprints (within leash)

## Build / test state

- **Full pytest:** `4861 passed`, `11 skipped`, `0 failed` (last run)
- **Ruff:** Green on sprint-touched Python files; JSON fixtures excluded from ruff scope
- **Alembic head:** `0019` (no new migrations in this block)
- **Stash:** Untouched
- **uv.lock:** Not staged or committed

## Stage 5 architecture (offline advisory chain)

Services layer in dependency order:

1. **Field confidence** (`funding_opportunity_intake_field_confidence_service.py`) — vocabulary + validation
2. **Field provenance** (`funding_opportunity_intake_field_provenance_service.py`) — per-field source lineage
3. **Opportunity record** (`funding_opportunity_intake_opportunity_record_service.py`) — provenance-first record shape
4. **Missing-data flags** (`funding_opportunity_intake_missing_data_flags_service.py`)
5. **Intake status** (`funding_opportunity_intake_status_service.py`)
6. **Fail-closed gates** (`funding_opportunity_intake_fail_closed_gates_service.py`) — blocks on missing deadline/source/provenance, stale deadline, unresolved duplicate without operator approval
7. **Operator duplicate detection** (`funding_opportunity_intake_operator_duplicate_detection_service.py`) — requires explicit operator approval
8. **Demo fixtures** (`funding_opportunity_intake_demo_fixture_service.py`) — repo-root `fixtures/funding_opportunity_intake/demo_records.json`
9. **Hardened record** (`funding_opportunity_intake_hardened_record_service.py`) — assembles full hardened preview
10. **Discovery bridge** (`funding_opportunity_intake_discovery_bridge_service.py`) — attaches `funding_opportunity_intake_hardening_preview` to discovery intake summaries via `discovery_intake_service.py`
11. **Confidence rollup** (`funding_opportunity_intake_confidence_rollup_service.py`)
12. **Operator review queue** (`funding_opportunity_intake_operator_review_queue_service.py`)
13. **Gate verification** (`funding_opportunity_intake_stage5_gate_verification_service.py`)
14. **Verification rollup** (`funding_opportunity_intake_stage5_verification_rollup_service.py`)
15. **Closeout packet** (`funding_opportunity_intake_stage5_closeout_packet_service.py`)

Key artifact types: `nf_funding_opportunity_field_confidence_v1`, `nf_funding_opportunity_record_v1`, `nf_funding_opportunity_hardened_record_v1`, `nf_funding_opportunity_stage5_verification_rollup_v1`, `nf_funding_opportunity_intake_stage5_closeout_packet_v1`.

## Key decisions

1. **Green baseline first:** Full suite green (`4834+` passed) before any Stage 5 feature commit.
2. **Fail-closed by default:** Gates block intake progression when deadline, source, provenance, staleness, or unresolved duplicate conditions are unmet; operator approval is the only path past duplicate holds.
3. **Synthetic-only corpus:** Demo records are static JSON fixtures — no network, no scraping, no source activation.
4. **Discovery integration is preview-only:** Intake summaries gain a hardened preview attachment; no persistence or execution side effects.
5. **Fixture path fix (Sprint 174):** `_FIXTURE_PATH` uses `parents[3]` from service module to resolve repo-root `fixtures/`.
6. **Terminology:** New code uses funding-opportunity language; no ContractForge/Spark branding in Stage 5 additions.

## Files changed (by theme)

- **Confidence / provenance / record (167–169):** 3 services + 3 tests
- **Flags / status / gates / duplicates (170–173):** 4 services + 4 tests
- **Fixtures / hardened record (174–175):** fixture JSON, 2 services + 2 tests
- **Bridge / rollup / queue (176–178):** 3 services, `discovery_intake_service.py` wiring, 3 tests
- **Verification / closeout (179–181):** 3 services + 3 tests

## Risks / needs human

- **Not pushed** — Mayhem review required before `git push`.
- **CLAUDE.md / AGENTS.md / uv.lock** remain untracked or unstaged locally.
- **Live ingestion** explicitly out of scope; Stage 5 is advisory preview until separate human authorization.
- **Operator duplicate workflow** requires explicit approval flag — no automatic merge/dedupe.

## Proposed next run

1. Push and review the 15 commits on `main`.
2. Operator walkthrough of Stage 5 verification rollup + demo fixture corpus.
3. Choose next lane: discovery UI surfacing of hardened preview, connector live-readiness planning, or documentation closeout.

## Verification commands

```bash
cd /home/josefgray/projects/nativeforge
source .venv/bin/activate
pytest -q
git log --oneline -15
git stash list   # confirm stash@{0} still present
pytest tests/test_sprint181_funding_opportunity_intake_stage5_closeout_packet.py -q
```
