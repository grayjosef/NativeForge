# NativeForge active source creation execution plan (v1)

## Sprint 60 purpose

Sprint 60 introduces `nf_active_source_creation_execution_plan_v1`, the **final preview-only** execution plan and evidence contract for **future** governed insertion of **exactly one** row into `nf_active_opportunity_sources`.

This sprint **consumes** the Sprint 59 artifact `nf_active_source_creation_execution_command_package_v1`. It **does not** replace upstream governance; it layers the single-row execution framing and evidence expectations on top of the chain built across Sprints 54–59.

## What Sprint 60 does

- Builds a deterministic, JSON-only execution plan (`build_active_source_creation_execution_plan`).
- Validates that a Sprint 59 command package is structurally acceptable for **future** execution review when readiness allows.
- Describes preview-only **future** execution steps, materialization intent, and evidence requirements (pre-execution, post-execution, rollback).

## What Sprint 60 does not do

- **No** insert, update, or delete on `nf_active_opportunity_sources` (or any table).
- **No** activation, scrape, ingest, external HTTP/API calls, LLM calls, or operator ledger actions.
- **No** Alembic upgrade/downgrade, schema mutation, or new migration revision.
- **No** database session open inside the Sprint 60 builder.
- **No** executable SQL strings, shell commands, Alembic CLI strings, or activation commands in the artifact.

Even when `readiness_decision` is `ready_for_future_single_source_row_creation_execution_review`, the artifact remains **review-only**: it authorizes **future human execution review** and evidence capture in a later sprint, not immediate writes.

## Relationship to Sprints 54–59

Sprint 60 preserves the discipline established earlier:

- **54**: empty-state / read-model alignment.
- **55**: active source creation **request** artifact.
- **56**: human **approval** intake.
- **57**: execution **dry-run** package.
- **58**: execution **readiness** gate.
- **59**: execution **command package** (preview-only).

Sprint 60 is the **terminal planning artifact** before the next sprint’s controlled execution evidence packet.

## Next sprint

The logical successor sprint produces the **first controlled active source creation execution evidence packet**: capturing pre/post snapshots, row identity, and rollback posture **after** explicit operator-approved execution — still outside Sprint 60’s non-execution boundary.
