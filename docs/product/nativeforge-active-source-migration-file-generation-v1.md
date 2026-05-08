# NativeForge active source migration file generation (v1)

## Purpose

Sprint 46 authors a **single** Alembic revision under `alembic/versions` that defines the future `nf_active_opportunity_sources` table, plus a deterministic `nf_active_source_migration_file_review_v1` payload that operators can inspect **without** applying migrations, writing database rows, activating sources, persisting approvals, scraping, ingesting, calling external APIs, or creating operator ledger actions.

Implementation:

- Revision module: `alembic/versions/0019_nf_active_opportunity_sources.py`
- Review service: `nativeforge.services.active_source_migration_file_review_service.build_active_source_migration_file_review`

## Relationship to Sprint 45 (Alembic migration generation gate)

Sprint 45 (`nf_alembic_migration_generation_gate_v1`) remains the planning gate that consumes Sprint 44 dry-run maps. After Sprint 46, the repository may contain **exactly one** filename matching `*nf_active_opportunity_sources*` under `alembic/versions`. The gate treats **at most one** matching path as structurally acceptable and records matches in `migration_file_absence_proof.matching_revision_files_found`. See [nativeforge-alembic-migration-generation-gate-v1.md](./nativeforge-alembic-migration-generation-gate-v1.md).

## Generated file

- Path: `alembic/versions/0019_nf_active_opportunity_sources.py`
- Revision id: `0019`
- Down revision: `0018` (current head before this table)
- Table: `nf_active_opportunity_sources`

## Migration file generation only boundary

Sprint 46 **creates migration source only**. No operator command executes `alembic upgrade` as part of this sprint’s deliverables. The review payload sets `migration_file_generation_only: true`, `actual_migration_apply_count: 0`, `may_run_alembic_upgrade_now: false`, and `may_apply_migration_now: false`.

## No migration apply / no database write / no activation boundary

The review payload enforces `actual_database_write_count: 0`, `actual_activation_count: 0`, `database_rows_written_now: false`, and `active_sources_created_now: false`. The migration module contains **no** row seeding helpers, **no** `bulk_insert`, and **no** row-level DML via `op.execute` (no inserts, updates, or row-targeted execute batches).

## Expected table fields (core)

Columns align with Sprint 43 `nf_active_source_schema_rollback_contract_v1` proposed fields and Sprint 44 field map intent, including governance columns (`legal_tos_review_required`, `provenance_capture_plan`, `freshness_cadence_days`, `dedupe_key_strategy`, `broad_eligibility_human_review_required`, `keyword_only_not_confirmed_eligible`), Native relevance basis, approval linkage placeholders, rollback linkage, disable metadata, and timestamps.

## Indexes and constraints

- **Unique identity per org:** `uq_nf_active_opportunity_sources_org_name_type_lane` on (`organization_id`, `source_name`, `source_type`, `source_lane`) — extends Sprint 43’s org + name + type idea with `source_lane` for Native-first lane isolation.
- **Health check:** `ck_nf_active_opportunity_sources_source_health_status` against `SourceHealthStatus` enum values.
- **Indexes (btree):** `organization_id`, `source_status`, `source_health_status`, `source_lane`, `source_type`, `last_checked_at`, `last_success_at`, `rollback_contract_id`.

## Upgrade and downgrade review requirements

Operators must confirm `upgrade()` only materializes `nf_active_opportunity_sources` and supporting indexes/constraints. `downgrade()` must retire indexes in reverse order, then retire the table via normal Alembic table teardown — without touching unrelated domain tables such as `nf_operator_actions`.

## Side-effect denial requirements

The review block `migration_absence_of_side_effects` must remain non-indicating for seeds, bulk row writes, operator ledger writes, ingestion triggers, and scraping triggers. Workbench-facing JSON continues to deny external side effects through `migration_application_boundary`.

## Provenance, freshness, dedupe, legal/TOS, Native relevance

- **Provenance:** `provenance_capture_plan` is required JSON with a safe empty default until operators attach a real plan.
- **Freshness:** `freshness_cadence_days` and `stale_threshold_days` carry conservative numeric defaults for schema-only creation; future activation sprints replace placeholders with operator-approved values.
- **Dedupe:** `dedupe_key_strategy` plus the org + name + type + lane unique key keep future matching deterministic per org.
- **Legal/TOS:** `legal_tos_review_required` defaults true; `public_access_basis` remains nullable pending legal review artifacts.
- **Native relevance:** `native_relevance_basis` is nullable until human review; lane + keyword governance booleans preserve **Native-first, not Native-only** doctrine (broad lanes still require explicit human review and never imply eligibility from keywords alone).

## Future pathway

After this sprint: **migration review sprint** (human schema diff + index/constraint audit) → **local migration verification sprint** (authorized `alembic upgrade` against disposable databases) → future approved active source creation (still governed by activation readiness, approval artifacts, and command dry-runs).
