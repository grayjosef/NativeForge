# NativeForge Handoff — Block NF-2: Native Relevance Classification v1 (Sprints 182–196)

**Date:** 2026-05-19  
**Branch:** `main` (ahead of `origin/main` by 16 commits)  
**Push:** Not performed (per governance)  
**Stash:** Preserved — `stash@{0}: wip-sprint8-ui-redesign-do-not-commit`

## Run summary

Completed the approved 15-sprint Stage 6 native relevance classification block with green baseline first. All work is preview-only, synthetic fixtures, advisory — no live ingestion, scraping, external URLs, LLM runtime, or source activation.

| Sprint | Commit | Summary |
|--------|--------|---------|
| 182 | `a5f1903` | Eight evidence-based classification labels + discoverable-label set |
| 183 | `8744b5e` | Per-label explanation templates (trigger language, entity types, gaps, operator next-check) |
| 184 | `cf3ef68` | Classification confidence vocabulary |
| 185 | `eb19db8` | Human-review trigger vocabulary |
| 186 | `1974526` | **Overclaim guard** — never `native_specific` without explicit source evidence |
| 187 | `a2debc2` | **Over-filter guard** — broad-relevant labels stay discoverable |
| 188 | `6f22453` | Synthetic demo fixture corpus (`fixtures/native_relevance_classification/demo_records.json`) |
| 189 | `2062bb8` | Deterministic classification evaluator (both invariants applied) |
| 190 | `dd10e76` | Per-classification explanation builder |
| 191 | `7717ca3` | Hardened classification record assembler |
| 192 | `fdcf531` | Discovery intake bridge — `native_relevance_classification_preview` on summaries |
| 193 | `31881f1` | Classification batch rollup |
| 194 | `39d09f2` | Operator review queue metadata |
| 195 | `3c70846` | Stage 6 gate verification on demo corpus |
| 196 | `38c045d` | Stage 6 native relevance classification closeout packet |

**Iterations used:** 15 product sprints (within leash)

## Build / test state

- **Full pytest:** `4905 passed`, `11 skipped`, `0 failed` (last run)
- **Ruff:** Green on sprint-touched Python files
- **Alembic head:** `0019` (no new migrations in this block)
- **Stash:** Untouched
- **uv.lock:** Not staged or committed

## Stage 6 architecture (offline advisory chain)

### Eight classification labels

1. `native_specific`
2. `tribal_government_specific`
3. `indigenous_community_relevant`
4. `native_entity_eligible_broad`
5. `broadly_eligible_potentially_relevant`
6. `weak_native_relevance`
7. `uncertain_relevance`
8. `irrelevant`

### Service chain

1. **Label vocabulary** (`native_relevance_classification_label_vocabulary_service.py`)
2. **Label explanations** (`native_relevance_classification_label_explanation_service.py`)
3. **Confidence** (`native_relevance_classification_confidence_service.py`)
4. **Human-review triggers** (`native_relevance_classification_human_review_trigger_service.py`)
5. **Overclaim guard** (`native_relevance_classification_overclaim_guard_service.py`)
6. **Over-filter guard** (`native_relevance_classification_over_filter_guard_service.py`)
7. **Demo fixtures** (`native_relevance_classification_demo_fixture_service.py`)
8. **Evaluator** (`native_relevance_classification_evaluator_service.py`) — applies both guards
9. **Explanation builder** (`native_relevance_classification_explanation_builder_service.py`)
10. **Record assembler** (`native_relevance_classification_record_service.py`)
11. **Discovery bridge** (`native_relevance_classification_discovery_bridge_service.py`) via `discovery_intake_service.py`
12. **Rollup** (`native_relevance_classification_rollup_service.py`)
13. **Operator review queue** (`native_relevance_classification_operator_review_queue_service.py`)
14. **Gate verification** (`native_relevance_classification_stage6_gate_verification_service.py`)
15. **Closeout packet** (`native_relevance_classification_stage6_closeout_packet_service.py`)

Key artifact types: `nf_native_relevance_classification_record_v1`, `nf_native_relevance_classification_stage6_gate_verification_v1`, `nf_native_relevance_classification_stage6_closeout_packet_v1`.

## Hard invariants (both tested)

1. **Overclaim guard:** `native_specific` requires explicit source evidence codes (`tribal_set_aside_in_source`, `tribal_eligible_in_source`, etc.). Without evidence, label is downgraded and `overclaim_blocked` triggers human review.
2. **Over-filter guard:** Labels in `DISCOVERABLE_LABELS` (all except `irrelevant`) cannot be marked non-discoverable; `final_discoverable` is forced true.

## Key decisions

1. **Green baseline first:** Full suite green (`4861` passed) before any Stage 6 feature commit.
2. **Synthetic-only corpus:** Nine demo fixtures cover all eight labels plus an overclaim-attempt case.
3. **Discovery integration is preview-only:** Intake summaries gain `native_relevance_classification_preview`; no persistence or execution side effects.
4. **Evaluator fail-closed:** Classification applies overclaim and over-filter guards on every record before rollup/queue/verification.
5. **Terminology:** Funding-opportunity / native-relevance language only; no ContractForge/Spark branding in Stage 6 additions.

## Risks / needs human

- **Not pushed** — Mayhem review required before `git push`.
- **AIRTABLE_TOKEN** not set in agent environment — `log_run.sh` calls skipped; operator should run locally.
- **Live classification** explicitly out of scope; Stage 6 is advisory preview until separate human authorization.

## Proposed next run

1. Push and review the 16 commits on `main` (15 feature + prior handoff baseline).
2. Operator walkthrough of Stage 6 gate verification + demo fixture corpus.
3. Choose next lane: discovery UI surfacing of classification preview, connector planning, or documentation closeout.

## Verification commands

```bash
cd /home/josefgray/projects/nativeforge
source .venv/bin/activate
pytest -q
git log --oneline -16
git stash list   # confirm stash@{0} still present
pytest tests/test_sprint196_native_relevance_classification_stage6_closeout_packet.py -q
```
