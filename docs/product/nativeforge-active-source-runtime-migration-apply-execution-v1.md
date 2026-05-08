# NativeForge active source runtime migration apply execution (v1)

## Sprint 52 purpose

Sprint 52 is the **controlled apply execution sprint** for Alembic revision **0019** (`nf_active_opportunity_sources`). Earlier sprints produced the migration file, local verification, apply planning, approval intake, readiness gate, and dry-run command package. Sprint 52 is authorized to run **only** `alembic upgrade 0019` (or equivalent, e.g. `uv run alembic upgrade 0019`) against an explicitly configured local or development database **after** preflight shows the database at down revision **0018**, or to record **already applied** when the database is already at **0019**.

## What this sprint does

- Preflight with `alembic current` (or equivalent).
- If current is **0018**, apply exactly **0019** — not `upgrade head` and not any other revision.
- If current is already **0019**, skip upgrade and record **already applied**.
- Post-apply checks: revision **0019**, table `nf_active_opportunity_sources` exists, **row count is 0**, and unrelated tables (for example `organizations` and `nf_opportunity_sources` when present) are still present.

## What this sprint does not do

- **No** creation of opportunity/source rows in registry or activation tables beyond what the empty DDL migration defines.
- **No** source activation, scraping, ingestion, external API calls, LLM calls, or operator ledger actions as part of the apply chain.
- **No** rollback unless a later sprint or runbook explicitly instructs it.

## Evidence artifact

Operator observations are captured in `nf_active_source_runtime_migration_apply_execution_v1` via `build_active_source_runtime_migration_apply_execution_evidence` in `active_source_runtime_migration_apply_execution_service.py`. The service does **not** run Alembic, subprocesses, or open database connections; it validates and packages **human-supplied** execution results.

## Row count zero

An empty `nf_active_opportunity_sources` table immediately after apply confirms the migration only introduced schema for future activation workflows — not seed data or activation.

## Rollback path

Downgrade to **0018** remains the documented rollback path; the evidence artifact records `rollback_path_preserved` when operators confirm that path is still valid for the environment.

## Next sprint

**Sprint 53** (or the next numbered verification sprint) should materialize the **post-apply verification artifact**: independent checks against baseline snapshots, application health, and operator sign-off that the schema change matches expectations without opening activation or data-movement paths.
