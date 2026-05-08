# NativeForge active source migration dry-run plan (v1)

## Purpose

The active source migration dry-run plan (`schema_version: nf_active_source_migration_dry_run_plan_v1`) is a deterministic, JSON-serializable pre-migration review package for the future `nf_active_opportunity_sources` table. It consumes `nf_discovery_source_quality_v1` and/or Sprint 43 `nf_active_source_schema_rollback_contract_v1`, then proposes planned upgrade and rollback steps, field/constraint/index migration maps, validation hooks, review gates, and explicit execution-boundary denials—without creating an Alembic revision, applying a migration, writing database rows, activating sources, persisting approvals, scraping, ingesting, calling external APIs, or creating operator ledger actions.

Implementation: `nativeforge.services.active_source_migration_dry_run_plan_service.build_active_source_migration_dry_run_plan`.

Integration: `build_discovery_source_quality` attaches `active_source_migration_dry_run_plan` after `active_source_schema_rollback_contract`, so operator Workbench `source_quality` payloads inherit the dry-run plan.

Sprint 45 attaches **`alembic_migration_generation_gate`** (`nf_alembic_migration_generation_gate_v1`) after the dry-run plan—see [nativeforge-alembic-migration-generation-gate-v1.md](./nativeforge-alembic-migration-generation-gate-v1.md).

## Schema overview

Top-level groups:

- `organization_scope`: org identity and generation timestamp carried from upstream payloads.
- `migration_plan_posture`: posture, counts, and **always-zero** actual migration/write/activation counters.
- `proposed_migration`: planned migration identity, table name, ordered upgrade/downgrade **dry-run** steps, and migration boundary flags.
- `field_migration_map`, `constraint_migration_map`, `index_migration_map`: deterministic maps sourced from Sprint 43 `proposed_active_source_schema`.
- `pre_migration_review_plan`, `migration_validation_plan`, `rollback_migration_plan`: review and validation structures with `dry_run_only: true` and `should_create_action: false`.
- `global_migration_boundary`: product-wide denial surface for migration execution, database writes, activation, ingestion, scraping, external APIs, and ledger actions.
- `sprint_44_execution_proof`: explicit evidence bundle that this sprint’s service layer does not create revisions or apply DDL.
- `risk_flags`, `summary`, `recommended_review_interval_days`.

## Relationship to Sprint 43 schema rollback contract

Sprint 44 reads Sprint 43 `proposed_active_source_schema` (`proposed_fields`, `proposed_unique_constraints`, `proposed_indexes`) and translates them into migration-planning artifacts. It does **not** reinterpret eligibility or activation semantics; it preserves Sprint 43 governance fields for provenance, freshness, dedupe, legal/TOS, broad eligibility human review, and keyword-not-confirmed eligibility.

See: [nativeforge-active-source-schema-rollback-contract-v1.md](./nativeforge-active-source-schema-rollback-contract-v1.md).

## Migration dry-run only boundary

`global_migration_boundary.migration_dry_run_only` is always `true`. `actual_migration_count`, `actual_database_write_count`, and `actual_activation_count` are always `0`. Every upgrade and downgrade step uses `dry_run_only: true` and `may_execute_now: false`.

## No Alembic revision from Sprint 44 service / no database write / no activation

The Sprint 44 **service** does not emit an Alembic revision module, does not apply migrations, and does not write rows. `alembic_revision_created_now` on the dry-run payload remains `false`. `may_generate_migration_now` and `may_apply_migration_now` stay `false`. Sprint 46 separately authors the revision file under `alembic/versions` while still forbidding apply from this planning layer—see [nativeforge-active-source-migration-file-generation-v1.md](./nativeforge-active-source-migration-file-generation-v1.md).

## Proposed migration shape

`proposed_migration_name` is `create_nf_active_opportunity_sources`. `proposed_table_name` is `nf_active_opportunity_sources`. `proposed_revision_status` is `dry_run_only_not_created`. `proposed_migration_type` is `create_table_future`. `proposed_dependency_revision` is recorded as `current_existing_head_or_unknown` until a future sprint resolves the live Alembic head.

Upgrade steps describe planning-only milestones (gate review, future table plan, column plan, constraint plan, index plan, validation hooks). Downgrade steps describe ordered rollback planning consistent with the Sprint 43 rollback contract, without authorizing execution in Sprint 44.

## Field migration map

Each Sprint 43 proposed field becomes a row with `migration_operation: add_column_future`, `dry_run_only: true`, and `may_apply_now: false`, plus contract references back to `nf_active_source_schema_rollback_contract_v1`.

## Constraint and index migration maps

Unique constraints and indexes are copied from Sprint 43 with `create_unique_constraint_future` and `create_index_future` operations. All rows remain dry-run only.

## Pre-migration review plan

`required_checks` include operator schema review, Sprint 43 contract review, rollback contract review, migration authorization, Alembic head verification, migration dry-run requirement, downgrade path review, constraint/index reviews, provenance/freshness/dedupe/legal/TOS/Native relevance reviews, no-live-ingestion during migration, and no customer-sensitive-data requirement for planning payloads.

`review_status` starts at `not_started`. `should_create_action` is `false`.

## Migration validation plan

Groups dry-run validation checks, post-generation checks (for a **future** migration generation sprint), post-apply checks (for a **future** apply), and rollback validation checks. All remain planning metadata; `should_create_action` is `false`.

## Rollback migration plan

The rollback plan mirrors Sprint 43 rollback obligations: operator approval, audit preservation, disabling sources before rollback, pausing ingestion, and explicit rollback boundary denials (`may_generate_rollback_migration_now: false`, `may_apply_rollback_now: false`, `may_drop_table_now: false`, `may_write_rollback_event_now: false`).

## Required operator and schema approvals

Future work requires operator schema stewardship review, schema owner review of constraints and indexes, and authorization for a dedicated migration generation sprint. Sprint 44 does not persist approvals.

## Provenance requirements

Field migration rows include provenance-related columns from Sprint 43. Pre-migration checks require provenance field review before any future migration generation.

## Freshness requirements

Freshness and health fields from Sprint 43 appear in the field map; validation planning references freshness monitoring boundaries without starting monitors.

## Dedupe requirements

Dedupe strategy fields and unique constraints from Sprint 43 appear in maps; Sprint 44 only plans future constraint materialization.

## Legal / TOS requirements

Legal/TOS review fields remain in the field map; review lists call out legal/TOS field review as a gate.

## Native relevance requirements

Broad eligibility human review and keyword-not-confirmed-eligible fields remain present as in Sprint 43. NativeForge stays **Native-first, not Native-only**: coverage breadth is allowed, but keyword-only Native relevance is not treated as confirmed eligibility in planning payloads.

## Native-first, not Native-only doctrine

The dry-run plan preserves governed breadth for discovery while keeping activation, migration execution, and eligibility confirmation strictly future-bound and human-reviewed.

## Future pathway to migration generation sprint

After this dry-run plan passes review, a **future** sprint may generate a real Alembic migration, subject to operator schema approval, rollback readiness, and activation execution policy. Sprint 44 explicitly sets `requires_future_migration_generation_sprint: true` and does not generate revisions.

## Related documents

- Sprint 43 schema and rollback contract: [nativeforge-active-source-schema-rollback-contract-v1.md](./nativeforge-active-source-schema-rollback-contract-v1.md)
- Activation command dry-run: [nativeforge-source-activation-command-dry-run-v1.md](./nativeforge-source-activation-command-dry-run-v1.md)
