# NativeForge Active Source Runtime Migration Apply Plan (`nf_active_source_runtime_migration_apply_plan_v1`)

## Sprint 48 purpose

Sprint 48 delivers a **deterministic human approval package** for a **future** operator-approved sprint that may apply Alembic revision **0019** (`alembic/versions/0019_nf_active_opportunity_sources.py`) to an explicitly identified runtime or shared database.

This sprint **does not**:

- Apply the migration to runtime, development, or production application databases.
- Create rows in `nf_active_opportunity_sources` or any activation path.
- Activate sources, seed data, scrape, ingest, call external APIs, call LLMs, or create operator ledger actions.
- Grant approval: approval form fields remain blank or null until a future apply sprint.

## Relationship to Sprint 46 and Sprint 47

- Sprint **46** authored the migration **file** (DDL only).
- Sprint **47** verified that file (`nf_active_source_local_migration_verification_v1`), including an isolated disposable-database gate where applicable.
- Sprint **48** defines **preflight, backup, rollback, post-apply validation, and human signoff requirements** before any real migration apply.

The apply-plan artifact requires Sprint 47 verification status **`passed`** (or equivalent `passed_*` embed posture) as a prerequisite signal inside the JSON bundle.

## Human approval and environment identification

No runtime migration apply is authorized from Sprint 48 code paths. A **future** apply sprint must:

- Identify the **target environment** and **target database identifier** explicitly.
- Complete every required approval field (operator identity, timestamps, backup acknowledgement, rollback review, downtime window where needed, post-apply validation owner, and approval statement).
- Refuse execution if those fields are incomplete or unreviewed.

## Rollback discipline

The plan embeds rollback expectations: downgrade to revision **0018**, verify removal of `nf_active_opportunity_sources`, preserve unrelated tables, confirm application and governance services load, and record rollback operator and timestamp in the apply sprint.

## Discovery source quality embedding

`build_discovery_source_quality()` may include `active_source_runtime_migration_apply_plan` as a **read-only governance signal** (JSON only). It does not persist operator approvals, open migration connections, or execute Alembic CLI commands.
